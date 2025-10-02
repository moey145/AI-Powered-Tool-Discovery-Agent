# Tool Scraper - AI-Powered Tool Discovery Agent

**Tool Scraper** is an intelligent AI-powered agent that helps developers discover, analyze, and compare developer tools, frameworks, and technologies. Built with a modern React frontend and FastAPI backend, it uses OpenAI GPT-4 and advanced web scraping to provide comprehensive tool insights in real-time.

---

## 🌟 Features

### 🔍 **Smart Tool Discovery**

- **Natural Language Search:** Describe what you need in plain English
- **AI-Powered Analysis:** GPT-4 extracts and analyzes relevant tools from search results
- **Real-Time Data:** Live web scraping ensures up-to-date information
- **Comprehensive Coverage:** Supports all types of developer tools and frameworks

### 📊 **Detailed Tool Analysis**

- **Pricing Models:** Free, Freemium, Paid, Enterprise classifications
- **Tech Stack Information:** Supported languages, frameworks, and technologies
- **API Availability:** Whether tools offer APIs for integration
- **Open Source Status:** Clear indication of licensing models
- **Integration Capabilities:** Available integrations and ecosystem support
- **Developer Experience Ratings:** AI-assessed ease of use and documentation quality

### 🎨 **Modern User Experience**

- **Responsive Design:** Works seamlessly on desktop, tablet, and mobile
- **Dark/Light Mode:** Toggle between themes with smooth transitions
- **Interactive UI:** Smooth animations, loading states, and progress indicators
- **Real-Time Feedback:** Live progress updates during analysis
- **Example Queries:** Pre-built suggestions to get started quickly

### ⚡ **Performance & Reliability**

- **Fast Response Times:** Optimized scraping and caching
- **Concurrent Processing:** Multiple tools analyzed simultaneously
- **Error Handling:** Graceful degradation and user-friendly error messages
- **Input Validation:** Comprehensive client and server-side validation
- **Security:** Protection against injection attacks and malicious content

---

## 🛠️ Tech Stack

### **Frontend**

- **React 19** with Vite for fast development and building
- **Custom CSS** with modern animations and responsive design
- **React Icons** for consistent iconography
- **React Toastify** for user notifications
- **EmailJS** for contact form functionality
- **Axios** for API communication

### **Backend**

- **FastAPI** for high-performance REST API
- **Python 3.11+** with modern async/await patterns
- **LangChain & LangGraph** for AI workflow orchestration
- **OpenAI GPT-4** for intelligent analysis and recommendations
- **BeautifulSoup4** for web scraping and content extraction
- **Pydantic** for data validation and serialization
- **AIOHTTP** for concurrent HTTP requests

### **AI & Search**

- **OpenAI GPT-4** for tool extraction and analysis
- **Google Custom Search API** for web search results
- **Advanced Web Scraping** with content filtering and validation
- **Intelligent Caching** for improved performance

---

## 📁 Project Structure

```
AI-Research-Agent/
├── advanced-agent/              # Backend (Python/FastAPI)
│   ├── src/
│   │   ├── workflow.py         # Main AI workflow with LangGraph
│   │   ├── models.py           # Pydantic data models
│   │   ├── prompts.py          # AI prompt templates
│   │   ├── fastscraper.py      # Web scraping service
│   │   ├── search_providers.py # Search API integrations
│   │   ├── query_expansion.py  # Query enhancement logic
│   │   ├── validators.py       # Input validation
│   │   ├── config.py           # Configuration management
│   │   └── logger.py           # Logging utilities
│   ├── api.py                  # FastAPI application
│   ├── main.py                 # CLI interface
│   ├── requirements.txt        # Python dependencies
│
├── react-frontend/              # Frontend (React/Vite)
│   ├── src/
│   │   ├── components/         # React components
│   │   │   ├── Hero.jsx        # Landing section
│   │   │   ├── Features.jsx    # Feature showcase
│   │   │   ├── SearchSection.jsx # Main search interface
│   │   │   ├── ResultsSection.jsx # Results display
│   │   │   ├── CompanyCard.jsx # Individual tool cards
│   │   │   ├── Contact.jsx     # Contact form
│   │   │   ├── Navbar.jsx      # Navigation
│   │   │   ├── Footer.jsx      # Footer
│   │   │   └── Toast*.jsx      # Notification system
│   │   ├── hooks/              # Custom React hooks
│   │   │   └── useSearch.js    # Search functionality
│   │   ├── contexts/           # React contexts
│   │   │   └── ThemeContext.jsx # Theme management
│   │   ├── utils/              # Utility functions
│   │   │   └── api.js          # API client
│   │   └── styles/             # Global styles
│   ├── public/                 # Static assets
│   ├── package.json            # Node.js dependencies
│   └── vite.config.js          # Vite configuration
│
├── Dockerfile                  # Container configuration
└── README.md                   # This file
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 16+**
- **OpenAI API Key** (required)
- **Google Custom Search API Key** (optional, for enhanced search)

### Backend Setup

1. **Navigate to backend directory:**

   ```bash
   cd advanced-agent
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   # or using uv (recommended)
   uv sync
   ```

3. **Set up environment variables:**

   Create a `.env` file in the `advanced-agent` directory with the following variables:

   ```bash
   # Create .env file
   touch .env
   ```

   Add these environment variables to your `.env` file:

   ```env
   # OpenAI API (required)
   OPENAI_API_KEY=your_openai_api_key_here

   # Google Custom Search API (optional, for enhanced search)
   GOOGLE_CUSTOM_SEARCH_API_KEY=your_google_api_key_here
   GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id_here

   # Search configuration
   SEARCH_PROVIDER=google_custom_search
   ```

   ⚠️ **Security Note:** Never commit API keys to the repository. Ensure `.env` files are in your `.gitignore`.

4. **Start the API server:**
   ```bash
   uvicorn api:app --reload --host 0.0.0.0 --port 8000
   # Server runs on http://localhost:8000
   ```

### Frontend Setup

1. **Navigate to frontend directory:**

   ```bash
   cd react-frontend
   ```

2. **Install dependencies:**

   ```bash
   npm install
   ```

3. **Start development server:**

   ```bash
   npm run dev
   # Frontend runs on http://localhost:5173
   ```

4. **Build for production:**
   ```bash
   npm run build
   ```

---

## 🔗 API Endpoints

### Core Endpoints

- `GET /health` - Health check and system status
- `POST /research` - Submit tool research queries
- `GET /examples` - Get example search queries

### Research Request Example

```json
{
  "query": "Python web frameworks for building APIs"
}
```

### Research Response Example

```json
{
  "companies": [
    {
      "name": "FastAPI",
      "description": "Modern, fast web framework for building APIs with Python",
      "website": "https://fastapi.tiangolo.com",
      "pricing_model": "Free",
      "is_open_source": true,
      "tech_stack": ["Python", "Pydantic", "Starlette"],
      "api_available": true,
      "language_support": ["Python"],
      "integration_capabilities": ["OpenAPI", "GraphQL", "WebSockets"]
    }
  ],
  "analysis": "Based on your query for Python web frameworks..."
}
```

---

## 🎯 Key Features Deep Dive

### **AI-Powered Workflow**

1. **Query Processing:** Natural language understanding and expansion
2. **Tool Extraction:** AI identifies relevant tools from search results
3. **Web Scraping:** Concurrent scraping of tool websites and documentation
4. **Analysis:** GPT-4 analyzes features, pricing, and suitability
5. **Recommendations:** Personalized suggestions based on requirements

### **Advanced Search Capabilities**

- **Query Expansion:** Automatically generates search variants
- **Multi-Provider Support:** Google Custom Search with fallback options
- **Content Filtering:** Intelligent filtering of relevant information
- **Caching:** Smart caching for improved performance

### **Security & Validation**

- **Input Sanitization:** Protection against XSS and injection attacks
- **Rate Limiting:** Prevents abuse and ensures fair usage
- **Error Handling:** Comprehensive error management and user feedback
- **Data Validation:** Pydantic models ensure data integrity

---

## 🎨 Customization

### **Frontend Customization**

- **Theme Colors:** Modify CSS variables in `src/styles/globals.css`
- **Component Styling:** Edit individual component CSS files
- **Feature Cards:** Customize in `Features.jsx` and `Features.css`
- **Search Interface:** Modify `SearchSection.jsx` for different layouts

### **Backend Customization**

- **AI Prompts:** Edit prompts in `src/prompts.py`
- **Search Providers:** Add new providers in `src/search_providers.py`
- **Data Models:** Extend models in `src/models.py`
- **Workflow Logic:** Modify the workflow in `src/workflow.py`

---

## 🧪 Usage Examples

### **Web Development**

- _"React state management libraries"_ → Redux, Zustand, Jotai analysis
- _"Node.js API frameworks"_ → Express, Fastify, Koa comparison
- _"CSS frameworks for rapid prototyping"_ → Tailwind, Bootstrap, Bulma

### **Data & Analytics**

- _"Python data visualization libraries"_ → Matplotlib, Plotly, Seaborn
- _"Time series databases"_ → InfluxDB, TimescaleDB, ClickHouse
- _"Machine learning frameworks"_ → TensorFlow, PyTorch, Scikit-learn

### **DevOps & Infrastructure**

- _"Container orchestration tools"_ → Kubernetes, Docker Swarm, Nomad
- _"CI/CD platforms"_ → GitHub Actions, GitLab CI, Jenkins
- _"Monitoring solutions"_ → Prometheus, Grafana, DataDog

---

## 🚀 Deployment

### **Docker Deployment**

```bash
# Build the container
docker build -t tool-scraper .

# Run the container
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e GOOGLE_CUSTOM_SEARCH_API_KEY=your_key \
  tool-scraper
```

### **Production Considerations**

- Set up proper environment variables
- Configure reverse proxy (nginx)
- Enable HTTPS
- Set up monitoring and logging
- Configure rate limiting
- Set up database for caching (optional)

---

## 📊 Performance Metrics

- **Average Response Time:** 10-25 seconds for comprehensive analysis
- **Concurrent Scraping:** Up to 10 tools analyzed simultaneously
- **Cache Hit Rate:** ~60% for repeated queries
- **Success Rate:** >95% for valid queries
- **Memory Usage:** ~200MB for backend, ~50MB for frontend

---

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch:** `git checkout -b feature/amazing-feature`
3. **Make your changes** and add tests if applicable
4. **Commit your changes:** `git commit -m 'Add amazing feature'`
5. **Push to the branch:** `git push origin feature/amazing-feature`
6. **Open a Pull Request**

### **Development Guidelines**

- Follow existing code style and patterns
- Add comprehensive error handling
- Include input validation
- Write clear commit messages
- Test your changes thoroughly

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🆘 Support

- **Documentation:** Check this README and inline code comments
- **Issues:** Report bugs and request features via GitHub Issues
- **Contact:** Reach out via the contact form in the application
- **Email:** mohamad.eldhaibi@gmail.com

---
