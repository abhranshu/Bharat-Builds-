# Project Status

## Overview
BharatHack is a web-based scroll-scrubbed image sequence project with frontend and backend components.

## Pending Work

### BharatHack Root Level
- [ ] **Empty backend folder**: The root `backend/` directory is empty - needs implementation or removal
- [ ] **Frame production**: Still need to create/animate actual frames for the scroll sequence
- [ ] **Asset pipeline**: Set up frame compression and storage in S3/CloudFront
- [ ] **Loading screen**: Build proper loading UI with progress indicator
- [ ] **Canvas implementation**: Wire up GSAP ScrollTrigger with canvas rendering

### UseItUp Folder
- [ ] **Backend review**: Need to review `UseItUp/backend/src/` contents to understand current implementation
- [ ] **Integration plan**: Define how `UseItUp` backend connects with the main BharatHack frontend
- [ ] **API endpoints**: Implement required APIs for frame serving/config management
- [ ] **Database setup**: If dynamic configuration is needed (frame counts, story points, etc.)
- [ ] **Testing**: Run backend tests to verify functionality

### Common Tasks
- [ ] **Environment setup**: Configure AWS credentials and SAM CLI for backend deployment
- [ ] **Git configuration**: Ensure `.gitignore` properly excludes large frame assets
- [ ] **Documentation sync**: Keep Info.md updated with actual project decisions

## Completed Work
- [x] Project scaffolding created
- [x] Info.md documentation written
- [x] Basic project structure established

## Notes
- Main scroll-scrub technique uses GSAP ScrollTrigger + Canvas API
- Backend is serverless (AWS Lambda + API Gateway via SAM)
- Frames should be stored in S3 with CloudFront distribution
