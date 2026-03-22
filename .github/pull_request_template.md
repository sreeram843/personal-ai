## Pull Request Checklist

- [ ] I have tested my changes locally with `docker compose up`
- [ ] Frontend builds without errors (`npm run build` in frontend/)
- [ ] Backend Python syntax is valid (no import errors)
- [ ] Docker image builds successfully
- [ ] I have updated documentation (README, comments) if needed
- [ ] My code follows the project's coding standards

---

## Description

<!-- Briefly describe your changes and their purpose -->

---

## Type of Change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update
- [ ] UI/UX improvement
- [ ] Performance improvement
- [ ] Refactoring

---

## Frontend Changes (if applicable)

- [ ] React components updated
- [ ] TypeScript types are correct
- [ ] Tailwind CSS classes applied
- [ ] No console warnings/errors
- [ ] Mobile responsive (tested on mobile view)

---

## Backend Changes (if applicable)

- [ ] FastAPI endpoints working correctly
- [ ] Pydantic schemas validate properly
- [ ] No breaking API changes
- [ ] Ollama/Qdrant integration tested (if applicable)
- [ ] Error handling in place

---

## Docker Changes (if applicable)

- [ ] Multi-stage build executes without errors
- [ ] Frontend dist is correctly copied
- [ ] Python dependencies install cleanly
- [ ] Container runs on port 8000
- [ ] All services (ollama, qdrant) start successfully

---

## Testing

How to test these changes:
1. Run `docker compose down` to clean up
2. Run `docker compose up --build` to rebuild
3. Test endpoints at `http://localhost:8000`
4. Verify UI in both Terminal and Classic modes

---

## Screenshots (if UI changes)

<!-- Add screenshots of the changes if applicable -->

---

## Additional Notes

<!-- Add any additional context or considerations here -->

---

By submitting this pull request, I confirm that my contribution follows the project's standards and will be licensed under the project's license.
