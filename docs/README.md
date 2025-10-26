# KaryaKarta Agent Documentation

Welcome to the KaryaKarta Agent documentation. This folder contains all essential documentation for the system.

## 📚 Documentation Index

### Core Documentation (5 Files)

1. **[API_CONTRACT.md](./API_CONTRACT.md)** - **THE SINGLE SOURCE OF TRUTH**
   - REST API endpoints and WebSocket protocol
   - Message formats and data models
   - Error handling and testing requirements
   - ⚠️ **ALL API changes MUST update this document first**

2. **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Complete system architecture
   - System design principles (SOLID)
   - Project structure and core components
   - Technology stack and future roadmap

3. **[README.md](./README.md)** - This file
   - Documentation hub and quick start
   - Integration checklists
   - Best practices

4. **[IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)** - Message tracking
   - Message ID tracking implementation
   - Session management details
   - Deduplication logic

5. **[PROJECT_STATUS.md](./PROJECT_STATUS.md)** - Current project status
   - Phase completion tracking
   - Available tools and capabilities
   - Performance optimization details
   - Next steps and roadmap

## 🚀 Quick Start

### For Frontend Developers

1. **Read API Contract**: [API_CONTRACT.md](./API_CONTRACT.md)
2. **Check Types**: See API_CONTRACT.md for TypeScript types
3. **Implement Message Tracking**: [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)
4. **Test Integration**: Use the examples in API_CONTRACT.md

**Key Points:**
- Generate unique `messageId` for each user message
- Include `messageId` and `sessionId` in API requests
- Implement deduplication for response messages
- Handle all message types (status, thinking, response, error)

### For Backend Developers

1. **Read Architecture**: [ARCHITECTURE.md](./ARCHITECTURE.md)
2. **Follow API Contract**: [API_CONTRACT.md](./API_CONTRACT.md)
3. **Check Current Status**: [PROJECT_STATUS.md](./PROJECT_STATUS.md)
4. **Review Implementation**: [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)

**Key Points:**
- Track processed message IDs
- Include `messageId` in ALL WebSocket messages
- Use smart compression (81% token cost reduction)
- Implement fast-fail fallback (78% faster)
- Return appropriate status codes

## 📋 Integration Checklist

### Frontend Implementation
- [ ] Install TypeScript types from [TYPESCRIPT_TYPES.md](./TYPESCRIPT_TYPES.md)
- [ ] Implement `generateMessageId()` function
- [ ] Implement `generateSessionId()` function
- [ ] Add message ID to all API requests
- [ ] Implement WebSocket connection
- [ ] Implement message deduplication logic
- [ ] Handle all message types (status, thinking, response, error)
- [ ] Implement session management (localStorage)
- [ ] Add error handling and retry logic
- [ ] Test integration with backend

### Backend Implementation
- [ ] Create project structure (folders created ✅)
- [ ] Implement Pydantic models matching API contract
- [ ] Add message ID tracking
- [ ] Implement deduplication logic
- [ ] Include `messageId` in all WebSocket messages
- [ ] Implement session management
- [ ] Add conversation memory
- [ ] Create generalist tools
- [ ] Add error handling
- [ ] Test all endpoints

## 🔄 Workflow

### Making API Changes

1. **Discuss**: Create GitHub issue to discuss the change
2. **Document**: Update [API_CONTRACT.md](./API_CONTRACT.md) first
3. **Version**: Increment version number if breaking change
4. **Implement**: Update backend and frontend code
5. **Test**: Ensure integration tests pass
6. **Deploy**: Deploy to staging, then production

### Keeping in Sync

**Daily:**
- Check [API_CONTRACT.md](./API_CONTRACT.md) before starting work
- Communicate any blockers or questions

**Before Deploying:**
- Verify API contract version matches between frontend/backend
- Run integration tests
- Check for breaking changes

**When Adding Features:**
- Update [API_CONTRACT.md](./API_CONTRACT.md)
- Update [TYPESCRIPT_TYPES.md](./TYPESCRIPT_TYPES.md) if needed
- Notify other team
- Update version numbers

## 📞 Communication

### For Questions
- API questions → Check [API_CONTRACT.md](./API_CONTRACT.md)
- Architecture questions → Check [ARCHITECTURE.md](./ARCHITECTURE.md)
- Type questions → Check [TYPESCRIPT_TYPES.md](./TYPESCRIPT_TYPES.md)
- Still confused → Create GitHub issue

### For Issues
- Tag with appropriate label: `api-contract`, `frontend`, `backend`, `types`
- Include API contract version number
- Provide example request/response if applicable

### For Breaking Changes
- **MUST** notify both teams 1 week in advance
- **MUST** update [API_CONTRACT.md](./API_CONTRACT.md)
- **MUST** increment major version (1.0.0 → 2.0.0)
- **MUST** maintain backward compatibility for 1 version

## 📊 Version History

### Current Versions
- API Contract: **1.0.0**
- Architecture: **1.0.0**
- TypeScript Types: **1.0.0**

### Changelog
See individual documentation files for detailed version history.

## 🛠️ Tools & Resources

### Backend Tools
- Python 3.10+
- FastAPI
- LangGraph
- Pydantic
- Playwright

### Frontend Tools
- Next.js 14+
- TypeScript
- Socket.IO
- React Hooks

### Testing
- Backend: pytest
- Frontend: Jest
- Integration: Both

## 🎯 Current Capabilities (Phase 4 Complete)

### Production-Ready Features ⭐
- **6 Tools**: search, browse, calculator, extractor, chunk_reader, list_tools
- **Smart Compression**: 81% token cost reduction (7,180 → 1,393 tokens)
- **Fast-Fail Fallback**: 78% faster scraper fallback (27s → 2.5s)
- **Content Chunking**: Automatic handling of large content
- **Session Management**: SQLite-based with conversation history

### Performance Metrics
- **Cost**: $0.005 per query (was $0.025) - 80% savings
- **Speed**: 2.5 seconds fallback (was 27 seconds)
- **Compression**: 99.8% HTML reduction with full context
- **Monthly Savings**: $200 on 10,000 queries

See [PROJECT_STATUS.md](./PROJECT_STATUS.md) for complete details.

## 📝 Documentation Updates

### When to Update
- **API Changes**: Update API_CONTRACT.md first
- **New Features**: Update PROJECT_STATUS.md
- **Architecture Changes**: Update ARCHITECTURE.md
- **Implementation Details**: Update IMPLEMENTATION_SUMMARY.md

### Standards
- Use clear, concise language
- Include code examples
- Update version numbers
- Notify affected teams

## 🎯 Goals

### Short-term (Current Sprint)
- Implement message ID tracking
- Add session management
- Create generalist tools
- Fix duplicate response issues

### Mid-term (Next Sprint)
- Enhanced tool suite
- Persistent memory
- Rate limiting
- Caching

### Long-term (Future)
- Google Docs integration
- Office 365 integration
- Multi-user support
- Advanced analytics

## 💡 Best Practices

### Performance Optimization
1. **Use Smart Compression**: Enabled by default, 81% cost reduction
2. **Monitor Token Usage**: Check `[SMART COMPRESS]` logs
3. **Configure Wisely**: Default 1500 tokens is optimal
4. **Track Costs**: See PROJECT_STATUS.md for cost formulas

### For Frontend
1. Always generate and track message IDs
2. Implement deduplication logic
3. Handle all message types (status, thinking, response, error)
4. Store session IDs in localStorage
5. Show loading states appropriately

### For Backend
1. Always include message IDs in responses
2. Use smart compression (automatic in scraper)
3. Maintain session context with memory service
4. Monitor performance metrics
5. Handle errors gracefully

### For Both
1. Follow API_CONTRACT.md strictly
2. Communicate changes early
3. Write tests for new features
4. Check PROJECT_STATUS.md for current capabilities

## 📚 Additional Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [Socket.IO Documentation](https://socket.io/docs/)
- [TypeScript Documentation](https://www.typescriptlang.org/docs/)

## 🤝 Contributing

1. Read relevant documentation
2. Follow coding standards
3. Write tests
4. Update documentation
5. Create pull request
6. Request review from both teams (if API change)

---

**Last Updated**: 2025-10-25  
**Maintained By**: KaryaKarta Development Team

For questions or feedback about this documentation, create a GitHub issue with the `documentation` label.
