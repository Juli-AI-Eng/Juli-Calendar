# Contributing to Juli Calendar Agent

Thank you for your interest in contributing to the Juli Calendar Agent! This document provides guidelines and information for contributors.

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please be respectful and considerate in all interactions.

## How to Contribute

### Reporting Issues

1. Check if the issue already exists in [GitHub Issues](https://github.com/Juli-AI/juli-calendar-agent/issues)
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)
   - Relevant logs or error messages

### Suggesting Features

1. Check existing issues and discussions for similar suggestions
2. Open a new issue with the "enhancement" label
3. Provide:
   - Use case and benefits
   - Proposed implementation approach (if applicable)
   - Examples of how it would work

### Submitting Pull Requests

1. **Fork the Repository**
   ```bash
   git clone https://github.com/your-username/juli-calendar-agent.git
   cd juli-calendar-agent
   ```

2. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Set Up Development Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -e .
   ```

4. **Make Your Changes**
   - Follow the code style guidelines
   - Add/update tests as needed
   - Update documentation if applicable

5. **Test Your Changes**
   ```bash
   # Run all tests
   pytest
   
   # Run specific test file
   pytest tests/unit/test_your_feature.py
   
   # Run with coverage
   pytest --cov=src tests/
   ```

6. **Format Your Code**
   ```bash
   # Install development dependencies
   pip install black isort mypy
   
   # Format code
   black src/ tests/
   isort src/ tests/
   
   # Type checking
   mypy src/
   ```

7. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "feat: add new feature
   
   - Detailed description of what changed
   - Why it was changed
   - Any breaking changes"
   ```

8. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create a pull request on GitHub.

## Development Guidelines

### Code Style

- **Python Style**: Follow PEP 8
- **Formatting**: Use Black with default settings
- **Import Sorting**: Use isort
- **Line Length**: Maximum 100 characters
- **Type Hints**: Required for all functions

### Documentation

- **Docstrings**: Required for all public functions and classes
- **Format**: Google-style docstrings
- **Example**:
  ```python
  def process_task(task_data: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
      """Process a task creation request.
      
      Args:
          task_data: Dictionary containing task details
          user_context: User context including timezone and credentials
          
      Returns:
          Dictionary with success status and created task details
          
      Raises:
          ValueError: If required fields are missing
          APIError: If external API call fails
      """
  ```

### Testing

- **Test Coverage**: Aim for >80% coverage
- **Test Types**:
  - Unit tests: Test individual functions/methods
  - Integration tests: Test component interactions
  - E2E tests: Test complete workflows

- **Test Naming**: `test_<function_name>_<scenario>`
- **Example**:
  ```python
  def test_process_task_with_valid_data():
      """Test task processing with valid input data."""
      # Arrange
      task_data = {"title": "Test task", "due": "tomorrow"}
      user_context = {"timezone": "America/New_York"}
      
      # Act
      result = process_task(task_data, user_context)
      
      # Assert
      assert result["success"] is True
      assert result["task"]["title"] == "Test task"
  ```

### Commit Messages

Follow conventional commits format:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation only
- `style:` Code style changes (formatting)
- `refactor:` Code restructuring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

### A2A Protocol Guidelines

When modifying A2A functionality:

1. **Maintain Backward Compatibility**: Don't break existing integrations
2. **Update Agent Card**: Reflect changes in `/.well-known/a2a.json`
3. **Document Changes**: Update A2A_DEVELOPER_GUIDE.md
4. **Test with Juli**: Ensure changes work with Juli Brain

### Tool Development Guidelines

When adding or modifying tools:

1. **Follow the 5-Tool Limit**: We maintain ≤5 tools for simplicity
2. **Clear Descriptions**: Every parameter must have a clear description
3. **Natural Language**: Tools should accept natural language input
4. **Approval Flows**: Operations affecting others need approval
5. **Error Handling**: Return clear, actionable error messages

## Review Process

### What We Look For

- **Code Quality**: Clean, readable, maintainable code
- **Tests**: Adequate test coverage
- **Documentation**: Clear documentation and comments
- **Performance**: No significant performance degradation
- **Security**: No security vulnerabilities introduced

### Review Timeline

- Initial review: Within 2-3 business days
- Follow-up reviews: Within 1-2 business days
- Small fixes: Usually same day

## Development Setup Tips

### Environment Variables

For development, create a `.env.local`:
```bash
# Development overrides
DEBUG=true
FLASK_ENV=development
LOG_LEVEL=DEBUG
```

### Debugging

```python
# Add debug logging
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Processing task: {task_data}")
```

### Common Issues

1. **Import Errors**: Ensure you've installed the package in editable mode: `pip install -e .`
2. **API Rate Limits**: Use mock responses in tests to avoid hitting API limits
3. **Async Issues**: Flask doesn't support async routes by default; use synchronous code

## Getting Help

- **Discord**: Join our [Discord community](https://discord.gg/juli-ai)
- **GitHub Discussions**: Ask questions in [Discussions](https://github.com/Juli-AI/juli-calendar-agent/discussions)
- **Email**: [support@juli.ai](mailto:support@juli.ai)

## Recognition

Contributors will be recognized in:
- The project README
- Release notes
- Our Discord community

Thank you for contributing to Juli Calendar Agent! 🎉