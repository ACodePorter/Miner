# StkGuru Demo Guide

## Quick Start

1. **Start the Miner Backend**
   ```bash
   # From the root directory
   ./Deploy/deploy.sh <your_tushare_key> DEV
   ```

2. **Start the StkGuru Frontend**
   ```bash
   cd StkGuru
   npm install
   npm run dev
   ```

3. **Open the Application**
   - Navigate to `http://localhost:5173`
   - You should see the PE Market Chart with SPX and QQQ data

## What You'll See

### PE Market Chart
- **Interactive Line Chart**: Shows historical PE ratios for S&P 500 and NASDAQ 100
- **Statistics Cards**: Display current PE, 20-year average, and min/max ranges
- **Hover Tooltips**: Detailed information when hovering over data points
- **Responsive Design**: Works on desktop and mobile devices

### Features
- **Real-time Data**: Fetches data from the Miner backend API
- **Professional Charts**: Built with Highcharts for financial data visualization
- **Error Handling**: Graceful error messages if API is unavailable
- **Loading States**: Clear loading indicators while fetching data

## API Integration

The application connects to these Miner backend endpoints:
- `GET http://localhost/api/market_pe?index=spx` - S&P 500 PE data
- `GET http://localhost/api/market_pe?index=qqq` - NASDAQ 100 PE data

## Troubleshooting

### No Data Displayed
1. Ensure the Miner backend is running (`http://localhost` should be accessible)
2. Check that PE data has been collected (run `/update_market_pe` endpoint)
3. Verify CORS settings in the backend allow `http://localhost:5173`

### Chart Not Loading
1. Check browser console for JavaScript errors
2. Verify Highcharts is properly installed
3. Ensure the API endpoints return valid JSON data

### Styling Issues
1. Clear browser cache
2. Restart the development server
3. Check that all CSS files are loading properly

## Next Steps

This is a foundation for the StkGuru application. Future enhancements could include:
- Additional market indicators (SMA, EMA, RSI, etc.)
- Stock price charts
- Market breadth visualization
- Portfolio tracking
- Real-time data updates
- Export functionality 