# 3GPP Downloader

A comprehensive tool for downloading 3GPP specification documents with both command-line and web interfaces.

## Features

- 🚀 **High-performance downloads** with multipart support and connection pooling
- 🕷️ **Intelligent scraping** of ETSI website for latest specifications
- 🌐 **Web UI** built with Mesop for easy management
- 🐳 **Docker support** for containerized deployment
- 📊 **Real-time progress** tracking and logging
- 🔄 **Automatic retry** with exponential backoff
- 📁 **Organized storage** by series and release

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd 3gpp-downloader

# Start with Docker Compose
docker-compose up -d
# Or with newer Docker versions:
docker compose up -d

# Open your browser to http://localhost:8080
```

### Option 2: Local Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run web interface
python run_web.py

# Or use command line
python -m src.main scrape download
```

## Usage

### Web Interface

1. Open http://localhost:8080 in your browser
2. Click "Start Scraping" to discover available specifications
3. Click "Filter Latest Versions" to get the most recent documents
4. Select files to download and click "Start Download"
5. Monitor progress in real-time through the web interface

### Command Line Interface

```bash
# Full pipeline: scrape and download
python -m src.main scrape download

# Only scrape for links
python -m src.main scrape

# Only download from existing links.json
python -m src.main download

# Filter to latest versions only
python -m src.main filter
```

## Project Structure

```
3gpp-downloader/
├── src/
│   ├── main.py                 # CLI entry point
│   ├── web_app.py             # Mesop web application
│   ├── tools/
│   │   ├── json_downloader.py # Core download logic
│   │   ├── etsi_spider.py     # Scrapy spider
│   │   └── monitored_pool.py  # Connection management
│   └── utils/
│       └── logging_config.py  # Logging setup
├── downloads/                 # Downloaded files (auto-created)
├── logs/                      # Application logs (auto-created)
├── requirements.txt           # Python dependencies
├── run_web.py                # Web UI launcher
├── Dockerfile                 # Docker image definition
├── docker-compose.yml         # Docker Compose configuration
└── README.md                  # This file
```

## Configuration

### Environment Variables

The application supports extensive configuration through environment variables. Copy `.env.example` to `.env` and modify values as needed:

```bash
cp .env.example .env
# Edit .env with your preferred settings
```

#### Key Configuration Areas:

- **Logging**: Separate log levels and files for each module
- **HTTP Client**: Connection pooling, timeouts, retry logic
- **Download**: Chunk sizes, multipart thresholds
- **Scrapy**: Request delays, concurrency limits
- **Web UI**: Port, logging, display options

### Command Line Arguments

```bash
# Full pipeline: scrape and download
python -m src.main scrape download

# Only scrape for links
python -m src.main scrape

# Only download from existing links.json
python -m src.main download

# Filter to latest versions only
python -m src.main filter
```

## Docker Deployment

### Build and Run

```bash
# Build the image
docker build -t gpp-downloader .

# Run the container
docker run -p 8080:32123 -v $(pwd)/downloads:/app/downloads gpp-downloader

# Or use Docker Compose
docker-compose up -d
# Or: docker compose up -d
```

### Persistent Storage

Downloads and logs are persisted in Docker volumes:
- `./downloads` - Downloaded PDF files
- `./logs` - Application log files

## Development

### Adding New Features

1. CLI features go in `src/main.py`
2. Web UI features go in `src/web_app.py`
3. Download logic in `src/tools/json_downloader.py`
4. Scraping logic in `src/tools/etsi_spider.py`

### Testing

```bash
# Install in development mode
pip install -e .

# Run tests
python -m pytest

# Check code quality
flake8 src/
mypy src/
```

## Troubleshooting

### Common Issues

1. **Port 8080 already in use**
   ```bash
   # Change port in docker-compose.yml
   ports:
     - "8081:32123"
   ```

2. **Permission errors**
   ```bash
   # Fix permissions on downloads directory
   sudo chown -R $USER:$USER downloads/
   ```

3. **Slow downloads**
   - Check your internet connection
   - The app automatically optimizes for your speed
   - Consider increasing timeouts in the code

### Logs

Check logs for detailed information:
```bash
# View application logs
tail -f logs/json_downloader.log

# View Docker logs
docker-compose logs -f
# Or: docker compose logs -f
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with [Mesop](https://google.github.io/mesop/) for the web interface
- Uses [aiohttp](https://docs.aiohttp.org/) for async downloads
- Powered by [Scrapy](https://scrapy.org/) for web scraping
- Containerized with Docker