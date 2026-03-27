# MeridianLogistics Development Patterns

> Auto-generated skill from repository analysis

## Overview

MeridianLogistics is a Python-based logistics management system with a focus on controller-based automation. The codebase follows conventional commit patterns and emphasizes comprehensive documentation, test-driven development, and systematic enum state management across models, policies, and documentation.

## Coding Conventions

### File Naming
- Use **kebab-case** for file names
  ```
  controller-models.py
  test-runtime.py
  autonomous-resume-plan.md
  ```

### Import Style
- Use **absolute imports** throughout the codebase
  ```python
  from backend.app.controller.models import ControllerState
  from backend.app.controller.policy import PolicyEngine
  ```

### Export Style
- Use **named exports** for classes and functions
  ```python
  class ControllerRuntime:
      pass
  
  def process_logistics_event():
      pass
  ```

### Commit Messages
- Follow **conventional commit** format with prefixes: `fix`, `docs`, `feat`, `test`, `chore`
- Keep messages around 49 characters
  ```
  feat: add autonomous resume capability
  fix: align enum states across models
  docs: update controller behavior in runbook
  ```

## Workflows

### Enum State Alignment
**Trigger:** When enum states need to be renamed or removed for consistency across the system
**Command:** `/align-enums`

1. **Update enum in models.py**
   ```python
   # backend/app/controller/models.py
   class ControllerState(Enum):
       ACTIVE = "active"
       PAUSED = "paused"  # renamed from "suspended"
   ```

2. **Update enum in policy.py**
   ```python
   # backend/app/controller/policy.py
   if controller.state == ControllerState.PAUSED:
       # handle paused state
   ```

3. **Update documentation references**
   - Search and replace enum references in `docs/plans/*.md`
   - Update state transition diagrams
   - Update API documentation

4. **Update test files to reflect new naming**
   ```python
   # tests/controller/test_states.py
   def test_controller_pause():
       assert controller.state == ControllerState.PAUSED
   ```

### Controller Feature Development
**Trigger:** When adding new controller functionality like autonomous resume or new logistics capabilities
**Command:** `/new-controller-feature`

1. **Create plan document**
   ```markdown
   # docs/plans/new-feature-plan.md
   ## Objective
   Implement [feature description]
   
   ## Implementation Steps
   - [ ] Runtime changes
   - [ ] Model updates
   - [ ] Testing strategy
   ```

2. **Add failing tests (TDD approach)**
   ```python
   # tests/controller/test_new_feature.py
   def test_autonomous_resume():
       # This test should fail initially
       assert controller.can_resume_autonomously()
   ```

3. **Implement runtime changes**
   ```python
   # backend/app/controller/runtime.py
   def enable_autonomous_resume(self):
       self.autonomous_mode = True
       self.log_state_change("autonomous_resume_enabled")
   ```

4. **Update controller models**
   ```python
   # backend/app/controller/models.py
   class ControllerConfig:
       autonomous_resume: bool = False
   ```

5. **Update documentation**
   - Add entry to `decisions.md`
   - Update `runbook.md` with new procedures
   - Update `reports/README.md` if reporting changes

6. **Verify all tests pass**
   ```bash
   python -m pytest tests/controller/
   ```

### Documentation Sync
**Trigger:** When controller behavior changes and documentation across multiple files needs alignment
**Command:** `/sync-docs`

1. **Update runtime implementation**
   ```python
   # backend/app/controller/runtime.py
   # Implement the behavioral change
   ```

2. **Update decisions.md**
   ```markdown
   ## Decision: [Date] - [Change Description]
   **Context:** Why this change was needed
   **Decision:** What was decided
   **Consequences:** Impact on system behavior
   ```

3. **Update runbook.md**
   - Add new operational procedures
   - Update troubleshooting sections
   - Revise monitoring guidelines

4. **Update reports/README.md**
   - Document new metrics or reports
   - Update report generation procedures

5. **Update agent prompts**
   ```markdown
   # .agents/agents/main.md
   ## Controller Behavior Updates
   - New behavior: [description]
   - Impact on automation: [details]
   ```

## Testing Patterns

### Test File Naming
- Use pattern `*.test.*` for test files
- Example: `controller.test.py`, `models.test.py`

### Test Structure
```python
def test_feature_name():
    # Arrange
    controller = setup_test_controller()
    
    # Act
    result = controller.perform_action()
    
    # Assert
    assert result.success == True
    assert controller.state == expected_state
```

## Commands

| Command | Purpose |
|---------|---------|
| `/align-enums` | Synchronize enumeration states across models, policies, and documentation |
| `/new-controller-feature` | Implement new controller functionality with TDD approach |
| `/sync-docs` | Update documentation across multiple files when behavior changes |
| `/commit-conventional` | Generate conventional commit message following project standards |
| `/test-controller` | Run controller-specific tests and validate functionality |