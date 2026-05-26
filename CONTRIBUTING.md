# Contributing to CommunityOne Open Navigatory

Thank you for your interest in contributing to the CommunityOne Open Navigatory project!!
 
## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue with:
- A clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, etc.)

### Suggesting Features

Feature requests are welcome! Please:
- Check if the feature has already been requested
- Clearly describe the feature and its use case
- Explain how it would benefit advocacy groups

### Code Contributions

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed

4. **Run tests**
   ```bash
   pytest
   black .
   ruff check .
   ```

5. **Commit your changes**
   ```bash
   git commit -m "Add feature: description"
   ```

6. **Push and create a pull request**
   ```bash
   git push origin feature/your-feature-name
   ```

## Code Style

- Follow PEP 8 guidelines
- Use type hints
- Write docstrings for all public functions
- Keep functions focused and single-purpose
- Use meaningful variable names

## Code of Conduct

This project values respectful, inclusive collaboration. We align with the principles of:
- **Open States Code of Conduct**: https://docs.openstates.org/code-of-conduct/
- Be respectful and professional
- Welcome diverse perspectives
- Focus on what's best for the community
- Show empathy towards other contributors

## Contributing to Upstream Projects

We use data and patterns from several open source civic tech projects. When contributing scraper patterns or improvements back to upstream projects like **OpenStates**, please:

1. **Follow their standards**: https://github.com/openstates/openstates-scrapers
2. **Reference their documentation**: https://docs.openstates.org/contributing/local-database/
3. **Respect their Code of Conduct**: https://docs.openstates.org/code-of-conduct/
4. **Test locally** before submitting pull requests
5. **Document data sources** used in scraper development

## Testing

All new features should include tests. Run the test suite with:

```bash
pytest tests/ -v
```

## Documentation

Update relevant documentation when:
- Adding new features
- Changing API endpoints
- Modifying configuration options
- Adding new dependencies

## Questions?

Open an issue or reach out to the maintainers.

Thank you for helping improve oral health advocacy! 🦷
