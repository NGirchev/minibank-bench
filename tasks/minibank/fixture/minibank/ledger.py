"""The ledger: accounts, postings and transfers (ADR-1, ADR-3, ADR-6, ADR-7)."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from .fx import RateTable, convert
from .money import Money, quantize

FEE_BPS = 50  # 0.5 %
MIN_FEE = {"USD": "0.50", "EUR": "0.50", "GBP": "0.40", "JPY": "70", "KWD": "0.150"}


@dataclass(frozen=True)
class Entry:
    seq: int
    account: str
    delta: Decimal
    currency: str
    at: datetime
    kind: str  # deposit | withdrawal | transfer_out | transfer_in | fee
    ref: str
    memo: str = ""


@dataclass
class Account:
    id: str
    currency: str
    owner: str


@dataclass(frozen=True)
class Transfer:
    ref: str
    src: str
    dst: str
    amount: Money
    credited: Money
    fee: Decimal
    rate: Decimal
    at: datetime


@dataclass
class Ledger:
    rates: RateTable
    accounts: dict[str, Account] = field(default_factory=dict)
    entries: list[Entry] = field(default_factory=list)
    transfers: dict[str, Transfer] = field(default_factory=dict)
    _seq: itertools.count = field(default_factory=itertools.count, repr=False)

    def open_account(self, account_id: str, currency: str, owner: str = "") -> Account:
        if account_id in self.accounts:
            raise ValueError(f"account exists: {account_id}")
        quantize(Decimal(0), currency)  # validates the currency
        account = Account(account_id, currency, owner)
        self.accounts[account_id] = account
        return account

    def _account(self, account_id: str) -> Account:
        try:
            return self.accounts[account_id]
        except KeyError:
            raise ValueError(f"unknown account: {account_id}") from None

    def _post(self, account: str, delta: Decimal, at: datetime, kind: str, ref: str, memo: str = "") -> Entry:
        if at.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        acc = self._account(account)
        entry = Entry(next(self._seq), account, quantize(delta, acc.currency), acc.currency, at, kind, ref, memo)
        self.entries.append(entry)
        return entry

    def _ref(self, prefix: str) -> str:
        return f"{prefix}-{len(self.entries) + 1:06d}"

    def deposit(self, account: str, amount: Money, at: datetime, memo: str = "") -> Entry:
        acc = self._account(account)
        if amount.currency != acc.currency or amount.amount <= 0:
            raise ValueError("deposit must be positive and in the account currency")
        return self._post(account, amount.amount, at, "deposit", self._ref("DEP"), memo)

    def withdraw(self, account: str, amount: Money, at: datetime, memo: str = "") -> Entry:
        acc = self._account(account)
        if amount.currency != acc.currency or amount.amount <= 0:
            raise ValueError("withdrawal must be positive and in the account currency")
        if self.balance(account) < amount.amount:
            raise ValueError("insufficient funds")
        return self._post(account, -amount.amount, at, "withdrawal", self._ref("WDR"), memo)

    def fee_for(self, src: Account, dst: Account, amount: Money) -> Decimal:
        """ADR-6: 0.5 % of the amount, at least MIN_FEE; free between accounts of one owner."""
        if src.owner and src.owner == dst.owner:
            return Decimal(0)
        fee = quantize(amount.amount * FEE_BPS / Decimal(10000), src.currency)
        return max(fee, Decimal(MIN_FEE[src.currency]))

    def transfer(self, src: str, dst: str, amount: Money, at: datetime, memo: str = "") -> Transfer:
        s, d = self._account(src), self._account(dst)
        if src == dst:
            raise ValueError("cannot transfer to the same account")
        if amount.currency != s.currency or amount.amount <= 0:
            raise ValueError("transfer amount must be positive and in the source currency")
        fee = self.fee_for(s, d, amount)
        if self.balance(src) < amount.amount + fee:
            raise ValueError("insufficient funds")
        rate = self.rates.rate(s.currency, d.currency, at)
        credited = convert(amount, d.currency, self.rates, at).rounded()
        ref = self._ref("TRF")
        self._post(src, -amount.amount, at, "transfer_out", ref, memo)
        if fee:
            self._post(src, -fee, at, "fee", ref, "transfer fee")
        self._post(dst, credited.amount, at, "transfer_in", ref, memo)
        transfer = Transfer(ref, src, dst, amount, credited, fee, rate, at)
        self.transfers[ref] = transfer
        return transfer

    def entries_for(self, account: str) -> list[Entry]:
        self._account(account)
        return sorted((e for e in self.entries if e.account == account), key=lambda e: (e.at, e.seq))

    def balance(self, account: str, at: datetime | None = None) -> Decimal:
        """Sum of the account's postings strictly before `at` (all postings when `at` is None)."""
        return sum((e.delta for e in self.entries_for(account) if at is None or e.at < at), Decimal(0))
