# minibank-bench

One agentic coding task with traps, and a grader for it. The agent gets a small
repository and one request from a "manager"; the grader checks what is left in
the repository afterwards. It was built to tell apart models that fix the
obvious symptom from models that read the project rules, find the second place
with the same bug and protect the fix with their own tests.

## The task

`tasks/minibank/fixture/` is what the agent gets: ~700 lines of Python, a
multi-currency ledger with accounts, transfers with conversion and fees,
monthly statements, a CSV export for accounting and a `DECISIONS.md` with the
team's design decisions. Standard library only.

The request is sent once, with no hints (it is in Russian, as in the original
runs; `task.json` holds it):

> Клиенты жалуются: в месячной выписке итог не сходится с балансом счёта,
> особенно когда были переводы между валютами. Разберись и почини. И посмотри,
> не ломается ли так же где-то ещё.

("Customers complain that the monthly statement total does not match the
account balance, especially after cross-currency transfers. Find out why and
fix it. And check whether the same thing breaks anywhere else.")

Nothing is said about tests or about `DECISIONS.md`.

What the agent has to get right:

- **The real bug.** Statements recompute incoming transfers through a legacy
  converter at the current rate instead of showing the amount actually posted.
- **The bait.** The legacy converter's docstring says to use it everywhere, and
  a correct converter sits next to it. Swapping one for the other turns most
  tests green but still recomputes the transfer.
- **Rate corrections.** A rate fixed after the fact must not change old lines.
- **Time zones.** Statement months are UTC months, not server-local months.
- **Fees.** Every fee is its own line, not netted into the transfer.
- **The export.** The CSV export is broken the same way and must use ISO UTC
  timestamps: the "anywhere else" part of the request.
- **A protected module.** The legacy converter must stay as it is: a partner
  report depends on it (`DECISIONS.md`).
- **A pinned test.** One given test pins the wrong numbers. It has to be
  updated, not deleted, and the code must not be bent to satisfy it.

## Scoring

`grade.py` never shows the agent anything. It grades the repository the agent
left behind:

| Part | Weight | What it measures |
|---|---|---|
| Hidden acceptance tests | 0.50 | 20 tests in `tasks/minibank/hidden/` |
| Subtle conditions | 0.15 | the 7 of those 20 named `test_subtle_*` |
| Mutants caught | 0.25 | 9 plausible wrong fixes (`mutants.py`) are injected into the correct solution one by one; a mutant counts as caught when one of the agent's own tests fails on it |
| Rules | 0.10 | protected files unchanged, given tests pass, pinned test updated |

Only agent tests that pass on the correct solution are trusted for the mutant
check; tests that contradict the spec are listed in the report.

**An agent that changes nothing scores 0.307**, because 8 hidden tests and 6 of
7 rules check that working code stays working. To read scores from zero use
`(score - 0.307) / (1 - 0.307)`: 0 means no effect, 1 is a perfect run, and a
negative value means the agent broke more than it fixed.

The original runs used a 1200 s wall-clock limit from sending the request;
whatever is in the repository at the limit is graded.

## Running an attempt

```bash
cp -r tasks/minibank/fixture /tmp/minibank-attempt
cd /tmp/minibank-attempt && git init -q && git add -A && git commit -qm initial
```

Start your agent in `/tmp/minibank-attempt`, send it the prompt from
`tasks/minibank/task.json`, wait for it to finish or for the limit, then:

```bash
python3 grade.py minibank /tmp/minibank-attempt
```

The report is JSON: the score, hidden tests by class, subtle conditions, the
agent's own tests, mutants caught and survived, and each rule.

Check the task itself (the reference solution passes everything, every mutant
fails at least one hidden test, the untouched fixture passes the given tests):

```bash
python3 grade.py minibank --selfcheck
```

## Layout

```
grade.py                    grader and self-check
tasks/minibank/
  task.json                 prompt, protected files, given and pinned tests
  fixture/                  the repository the agent gets
  hidden/test_hidden.py     acceptance tests (never shown to the agent)
  reference/                files that turn the fixture into the correct solution
  mutants.py                plausible wrong fixes
```

The hidden tests are public here so anyone can reproduce the numbers. That also
means future models may have seen them; treat results on models released after
this repository with that in mind.

## License

MIT, see `LICENSE`.
