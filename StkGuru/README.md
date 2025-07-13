# StkGuru - Stock Market Data Visualization

A React-based frontend application for visualizing financial market data from the Miner project.

## Features

- **Market PE Ratios Chart**: Interactive line chart showing S&P 500 (SPX) and NASDAQ 100 (QQQ) Price-to-Earnings ratios over time
- **Real-time Data**: Fetches data from the Miner backend API
- **Responsive Design**: Works on desktop and mobile devices
- **Interactive Charts**: Built with Highcharts for professional financial data visualization

## Prerequisites

- Node.js (v16 or higher)
- The Miner backend service running on `http://localhost`

## Installation

1. Navigate to the StkGuru directory:
```bash
cd StkGuru
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

4. Open your browser and navigate to `http://localhost:5173`

## API Endpoints Used

The application connects to the Miner backend API:

- `GET /api/market_pe?index=spx` - Get S&P 500 PE data
- `GET /api/market_pe?index=qqq` - Get NASDAQ 100 PE data

## Features

### PE Market Chart
- Displays historical PE ratios for both SPX and QQQ
- Shows current PE, 20-year average, and min/max ranges
- Interactive tooltips with detailed information
- Responsive design that works on all screen sizes

## Troubleshooting

### Chrome Browser Issues

If you encounter errors in Chrome like:
- `Failed to execute 'put' on 'Cache': Request scheme 'chrome-extension' is unsupported`
- Blank page or React hook errors
- WebSocket connection failures

**Solutions:**

1. **Clear Browser Cache and Service Workers:**
   - Visit `http://localhost:5173/clear-cache.html` to automatically clear service workers and cache
   - Or manually clear browser cache: Chrome Settings → Privacy and Security → Clear browsing data

2. **Disable Browser Extensions:**
   - Try opening Chrome in incognito mode (which disables extensions)
   - Disable ad blockers, PWA installers, or other extensions that might interfere

3. **Hard Refresh:**
   - Press `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac) to force reload

4. **Check Network Tab:**
   - Open Chrome DevTools (F12)
   - Check the Network tab for failed requests
   - Ensure the backend API is running on `http://localhost`

### Common Issues

**No Data Displayed:**
1. Ensure the Miner backend is running (`http://localhost` should be accessible)
2. Check that PE data has been collected (run `/update_market_pe` endpoint)
3. Verify CORS settings in the backend allow `http://localhost:5173`

**Chart Not Loading:**
1. Check browser console for JavaScript errors
2. Verify Highcharts is properly installed
3. Ensure the API endpoints return valid JSON data

**Styling Issues:**
1. Clear browser cache
2. Restart the development server
3. Check that all CSS files are loading properly

## Development

### Project Structure
```
src/
├── components/
│   ├── MarketPeChart.tsx    # PE ratio chart component
│   ├── MarketBreathChart.tsx # Market breadth chart component
│   ├── ErrorBoundary.tsx    # Error handling component
│   ├── LoadingSpinner.tsx   # Loading component
│   └── ErrorMessage.tsx     # Error display component
├── App.tsx                  # Main application component
├── App.css                  # Application styles
├── main.tsx                 # Application entry point
└── index.css                # Global styles
```

### Adding New Charts

To add new chart components:

1. Create a new component in the `src/components/` directory
2. Import and use Highcharts for visualization
3. Add the component to `App.tsx`
4. Style as needed

### Building for Production

```bash
npm run build
```

This creates a production build in the `dist/` directory.

## Technologies Used

- **React 19** - UI framework
- **TypeScript** - Type safety
- **Highcharts** - Professional charting library
- **Vite** - Build tool and dev server
- **CSS3** - Styling

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

Apache License 2.0
