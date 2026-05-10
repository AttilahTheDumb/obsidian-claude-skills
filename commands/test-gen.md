---
description: Behaviour-first test generation — analyses what code promises to do, then writes tests that catch real bugs
model: opus
allowed-tools: Read, Write, Edit, Bash, Glob, AskUserQuestion
---

# /test-gen — Behaviour-First Test Generation

Generates meaningful tests by reasoning about *what code promises to do*, not just what functions exist. Matches your existing test style, covers edge cases you haven't thought of, and runs the tests to verify they pass.

---

## Instructions for Claude

### Guiding principle

The difference between useful tests and useless tests is **behavioural thinking**.

Bad test generation: "There's a function called `calculateDiscount`, so I'll write `test_calculateDiscount`."

Good test generation: "This function promises that:
- Discounts never exceed 100%
- A zero-value order gets no discount
- VIP status stacks with promotional codes, up to the cap
- Invalid inputs throw, they don't silently return wrong values"

Every test you write must exist because it catches a specific, realistic bug. If you can't articulate what bug a test would catch, don't write it.

---

### Step 1: Identify the target

Check whether the user provided a file path or function name as an argument to `/test-gen`.

**If a target was provided**, proceed to Step 2.

**If no target was provided**, call AskUserQuestion:

- **question:** "What would you like to generate tests for?"
- **header:** "Test target"
- **multiSelect:** false
- **options:**
  1. `{ label: "A specific file", description: "Generate tests for an entire source file" }`
  2. `{ label: "A specific function or class", description: "Target one function, class, or module" }`
  3. `{ label: "Find least-tested code", description: "I'll scan your project and suggest what most needs tests" }`

If the user selects "Find least-tested code":
- Run `find . -name "*.test.*" -o -name "*_test.*" -o -name "test_*.py" 2>/dev/null` to find existing tests
- Run `find . -type f \( -name "*.py" -o -name "*.ts" -o -name "*.js" -o -name "*.go" -o -name "*.rb" \) ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/vendor/*" 2>/dev/null` to find source files
- Identify source files with no corresponding test file
- Present the top 3 candidates and ask which to test

---

### Step 2: Detect the project environment

Run these in parallel to understand the project:

```bash
# Language and framework signals
ls package.json pyproject.toml go.mod Cargo.toml Gemfile pom.xml composer.json 2>/dev/null
cat package.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps({**d.get('devDependencies',{}), **d.get('scripts',{})}, indent=2))" 2>/dev/null
cat pyproject.toml 2>/dev/null | head -40
find . -name "jest.config.*" -o -name "vitest.config.*" -o -name "pytest.ini" -o -name ".rspec" -o -name "phpunit.xml" 2>/dev/null | head -5
```

Determine:
- **Language**: Python / TypeScript / JavaScript / Go / Ruby / Rust / Java / PHP
- **Test framework**: Jest / Vitest / Mocha / pytest / unittest / Go testing / RSpec / Minitest / JUnit / PHPUnit / Rust test
- **Test runner command**: `npm test`, `pytest`, `go test ./...`, `bundle exec rspec`, etc.
- **Test file naming convention**: `*.test.ts`, `*_test.go`, `test_*.py`, `*_spec.rb`, etc.
- **Test file location**: co-located (`src/foo.test.ts`), `__tests__/`, `tests/`, `spec/`

---

### Step 3: Read the target code

Read the target file completely. As you read, build a mental model of:

**Contracts** — what does this code *promise*?
- Return values: what does it return and under what conditions?
- Side effects: what does it write, emit, or mutate?
- Errors: when does it throw/return errors, and what kind?
- Dependencies: what external things does it call (database, API, filesystem, time, random)?

**Boundaries** — where do things change?
- Numeric: zero, negative, maximum, minimum, overflow
- Collections: empty, one item, many items, duplicates
- Strings: empty, whitespace-only, very long, special characters, unicode
- State: uninitialized, partially initialized, already completed

**Failure modes** — what could go wrong?
- Missing or null inputs
- External dependency failures (network down, DB error)
- Concurrent access
- Invalid state combinations

---

### Step 4: Study existing test style

Find 2–3 existing test files in the project:

```bash
find . -name "*.test.*" -o -name "*_test.*" -o -name "test_*.py" -o -name "*_spec.rb" 2>/dev/null | grep -v node_modules | grep -v vendor | head -5
```

Read them and extract:
- **Naming pattern**: `it('should ...')` vs `test('...')` vs `def test_verb_noun_condition()`
- **Assertion style**: `expect(x).toBe(y)` vs `assert x == y` vs `assert_equal`
- **Setup pattern**: `beforeEach` / `setUp` / fixtures / factories
- **Mocking pattern**: `jest.mock` / `unittest.mock.patch` / `stub` / `spy`
- **Test grouping**: `describe` blocks, test classes, modules
- **Data style**: inline literals, fixtures, factories, faker

If no existing tests exist, use idiomatic conventions for the detected framework.

---

### Step 5: Build the test plan

Before writing any code, produce a structured test plan. Output this to the conversation so the user can see your reasoning:

```
## Test Plan: [filename]

### Behaviours identified
1. [Behaviour 1 — what the code promises]
2. [Behaviour 2]
...

### Test cases

**[Behaviour 1]**
- ✅ Happy path: [description]
- ⚠️  Edge case: [description] — catches: [what bug this would catch]
- ❌ Error case: [description] — catches: [what bug this would catch]

**[Behaviour 2]**
- ✅ Happy path: [description]
- ⚠️  Edge case: [description]
...

### Mocking required
- [Dependency]: [why it needs mocking and how]

### Estimated test count: [N]
```

Then ask:

Call AskUserQuestion:
- **question:** "Ready to generate [N] tests for [filename]. Proceed?"
- **header:** "Confirm"
- **multiSelect:** false
- **options:**
  1. `{ label: "Generate all tests", description: "Write the full test suite now" }`
  2. `{ label: "Generate happy paths only", description: "Start with the core cases, skip edge cases" }`
  3. `{ label: "Adjust the plan first", description: "Let me give feedback before generating" }`

---

### Step 6: Generate the tests

Write tests following these rules:

**Test names must describe behaviour, not implementation:**
- ✅ `it('returns empty array when no users match the filter')`
- ❌ `it('tests getUsers')`
- ✅ `def test_discount_cannot_exceed_100_percent()`
- ❌ `def test_calculate_discount()`

**Each test must have one reason to fail:**
- One assertion per logical concept (multiple `expect` calls for the same concept is fine, multiple unrelated concepts is not)

**Use realistic test data:**
- ✅ `{ email: 'alice@example.com', role: 'admin' }`
- ❌ `{ email: 'test', role: 'foo' }`

**Comment groups, not lines:**
- Add a one-line comment before each `describe` block or logical group explaining what category of behaviour it tests and what bugs the group would catch
- Do NOT comment individual assertions unless the logic is non-obvious

**Mock at the boundary, not the internals:**
- Mock external I/O (network, filesystem, database, time, randomness)
- Do NOT mock the code being tested
- Do NOT mock internal helpers within the same module unless they have external dependencies

**Handle async correctly:**
- Use the framework's async conventions (`async/await`, `asyncio`, goroutines with `t.Run`)

---

### Step 7: Determine the output file path

Follow the project's conventions:

- If tests are co-located: write to `same/directory/as/source/[name].test.[ext]`
- If tests are in `__tests__/`: mirror the source path under `__tests__/`
- If tests are in `tests/` or `spec/`: mirror the source directory structure
- If it's Go: write to `[source_file]_test.go` in the same package
- If no convention is clear: default to co-located

Check whether a test file already exists at that path. If it does:
- Read it first
- Append new test cases rather than overwriting
- Avoid duplicate test names

---

### Step 8: Write the test file

Write the complete test file. Then output a brief summary to the conversation:

```
## Tests written

📁 [path/to/test/file]
[N] tests across [M] behaviours

Categories covered:
- Happy paths ([n] tests)
- Edge cases ([n] tests)
- Error handling ([n] tests)
- Boundary conditions ([n] tests)

Notable cases:
- "[test name]" — catches [specific bug type]
- "[test name]" — catches [specific bug type]
```

---

### Step 9: Run the tests

Execute the test runner, scoped to the new test file where possible:

| Framework | Run command |
|-----------|-------------|
| Jest | `npx jest [test-file-path] --no-coverage` |
| Vitest | `npx vitest run [test-file-path]` |
| pytest | `python -m pytest [test-file-path] -v` |
| Go | `go test ./[package]/...` |
| RSpec | `bundle exec rspec [test-file-path]` |
| Cargo | `cargo test` |
| PHPUnit | `./vendor/bin/phpunit [test-file-path]` |

Report results:

**If all pass:**
```
✅ All [N] tests passed

Run again any time: [test command]
```

**If some fail:**
Analyse each failure carefully. Determine whether the failure is because:

1. **The test is wrong** — fix the test (bad expectation, wrong mock, test data issue)
2. **The code has a bug** — report it clearly: "Found a real bug: [description]. The test is correct."
3. **Missing setup** — fix the setup (missing dependency, environment variable, seed data)

Fix category 1 and 3 automatically, re-run, and report. For category 2, leave the failing test in place and clearly flag it as a discovered bug.

**Final output:**
```
## Results

✅ [N] passed  ❌ [M] failed  ⚠️  [K] skipped

[If bugs found:]
🐛 Real bugs discovered:
- [description of bug, line number, suggested fix]

Run tests: [command]
```

---

### What makes a great test suite (internal checklist)

Before finalising, verify:
- [ ] Every test name reads as a sentence describing a behaviour
- [ ] No test is testing the framework itself (e.g., `expect(true).toBe(true)`)
- [ ] Edge cases cover: empty, null/undefined, zero, negative, very large, wrong type
- [ ] Error cases verify the *type* of error, not just that an error occurred
- [ ] Mocks are reset between tests (no test pollution)
- [ ] No test depends on the order of other tests
- [ ] Test data is realistic and varied (not all `'foo'` and `1`)
- [ ] At least one test would fail if the core logic were deleted
