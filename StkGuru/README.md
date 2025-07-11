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

## Development

### Project Structure
```
src/
├── components/
│   └── PEMarketChart.tsx    # PE ratio chart component
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
