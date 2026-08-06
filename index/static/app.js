(function () {
  const DEFAULT_API_BASE = '/tv';
  const DEFAULT_SYMBOL = 'BTCIRT';
  const DEFAULT_RESOLUTION = '15';

  const config = {
    apiBase: window.NOBITEX_TV_API_BASE || DEFAULT_API_BASE,
    defaultSymbol: window.NOBITEX_TV_DEFAULT_SYMBOL || DEFAULT_SYMBOL,
    defaultResolution: window.NOBITEX_TV_DEFAULT_RESOLUTION || DEFAULT_RESOLUTION,
    exchange: 'Nobitex'
  };

  function normalizeSymbol(symbol) {
    return String(symbol || '').trim().toUpperCase().replace(/[-\/\s]/g, '');
  }

  function resolutionToSeconds(resolution) {
    const r = String(resolution).toUpperCase();
    if (r === '1') return 60;
    if (r === '3') return 180;
    if (r === '5') return 300;
    if (r === '15') return 900;
    if (r === '30') return 1800;
    if (r === '60') return 3600;
    if (r === '180') return 10800;
    if (r === '240') return 14400;
    if (r === '360') return 21600;
    if (r === '720') return 43200;
    if (r === 'D' || r === '1D') return 86400;
    if (r === '2D') return 172800;
    if (r === '3D') return 259200;
    if (r === 'W') return 604800;
    if (r === 'M') return 2592000;
    return 60;
  }

  async function api(action, params = {}) {
    const isAbsoluteUrl = config.apiBase.startsWith('http');
    const baseUrl = isAbsoluteUrl ? config.apiBase : window.location.origin + config.apiBase;
    
    const url = new URL(`${baseUrl}/${action}`);

    let safeExchange = String(config.exchange || '').trim();
    if (!safeExchange || safeExchange.toLowerCase() === 'undefined' || safeExchange.toLowerCase() === 'null' || safeExchange === '') {
        safeExchange = 'Nobitex';
    }
    
    config.exchange = safeExchange;

    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        url.searchParams.set(k, String(v));
      }
    });

    if (action !== 'server-time' && action !== 'exchanges') {
        url.searchParams.set('exchange', safeExchange);
    }

    const res = await fetch(url.toString(), { cache: 'no-store' });
    const data = await res.json();
    
    if (!res.ok || data.s === 'error') {
      throw new Error(data.errmsg || data.error || `HTTP ${res.status}`);
    }
    return data;
  }

  function makeBar(raw) {
    return {
      time: Number(raw.time),
      open: Number(raw.open),
      high: Number(raw.high),
      low: Number(raw.low),
      close: Number(raw.close),
      volume: Number(raw.volume || 0),
    };
  }

  function inferPricescale(symbol, lastPrice) {
    const s = normalizeSymbol(symbol);
    if (s.endsWith('IRT')) return 1;
    if (s.endsWith('USDT')) return 1000000;
    if (s.endsWith('BTC')) return 100000000;
    if (typeof lastPrice === 'number' && Number.isFinite(lastPrice)) {
      const txt = String(lastPrice);
      if (txt.includes('.')) {
        const dec = txt.split('.')[1].replace(/0+$/, '');
        return Math.max(1, Math.pow(10, Math.min(8, dec.length)));
      }
    }
    return 1000000;
  }

  class MultiExchangeDatafeed {
    constructor() {
      this.subscriptions = new Map();
      this.cache = new Map();
      this.supported = ['1', '5', '15', '30', '60', '180', '240', '360', '720', 'D', '2D', '3D', 'W', 'M'];
    }

    onReady(callback) {
      setTimeout(() => {
        callback({
          supported_resolutions: this.supported,
          supports_search: true,
          supports_group_request: false,
          supports_marks: false,
          supports_timescale_marks: false,
          supports_time: true,
          exchanges: [{ value: config.exchange, name: config.exchange.toUpperCase(), desc: config.exchange }],
          symbols_types: [{ name: 'Crypto', value: 'crypto' }],
        });
      }, 0);
    }

    searchSymbols(userInput, exchange, symbolType, onResultReadyCallback) {
      api('search', { query: userInput })
        .then((data) => {
          const symbols = (data.symbols || []).map((item) => ({
            symbol: item.symbol,
            full_name: item.full_name,
            description: item.description,
            exchange: item.exchange || config.exchange,
            ticker: item.ticker,
            type: item.type || 'crypto',
          }));
          onResultReadyCallback(symbols);
        })
        .catch(() => onResultReadyCallback([]));
    }

    resolveSymbol(symbolName, onSymbolResolvedCallback, onResolveErrorCallback) {
      const symbol = normalizeSymbol(symbolName);
      api('resolve', { symbol })
        .then((data) => {
          const lastPrice = data.last_price;
          onSymbolResolvedCallback({
            name: data.name,
            ticker: data.ticker,
            description: data.description,
            type: data.type || 'crypto',
            session: data.session || '24x7',
            timezone: data.timezone || 'Asia/Tehran',
            exchange: data.exchange || config.exchange,
            listed_exchange: data.listed_exchange || config.exchange,
            format: data.format || 'price',
            minmov: data.minmov || 1,
            pricescale: data.pricescale || inferPricescale(symbol, lastPrice),
            has_intraday: true,
            has_daily: true,
            has_weekly_and_monthly: true,
            supported_resolutions: data.supported_resolutions || this.supported,
            volume_precision: data.volume_precision || 8,
            data_status: data.data_status || 'streaming',
          });
        })
        .catch((err) => {
          onResolveErrorCallback(err.message || 'resolveSymbol failed');
        });
    }

    getBars(symbolInfo, resolution, periodParams, onHistoryCallback, onErrorCallback) {
      const symbol = normalizeSymbol(symbolInfo.ticker || symbolInfo.name || symbolInfo.symbol);
      let from = periodParams.from || 0;
      let to = periodParams.to || Math.floor(Date.now() / 1000);

      const countback = periodParams.countBack || periodParams.countback;

      if (countback) {
        const seconds = resolutionToSeconds(resolution);
        const safeFrom = to - (countback * seconds * 2);
        if (from > safeFrom) {
          from = safeFrom;
        }
      }

      api('history', { symbol, resolution, from, to })
        .then((data) => {
          const bars = (data.bars || []).map(makeBar);
          if (!bars.length) {
            onHistoryCallback([], { noData: true });
            return;
          }

          this.cache.set(symbol + ':' + resolution, bars[bars.length - 1]);
          onHistoryCallback(bars, { noData: false });
        })
        .catch((err) => {
          onErrorCallback(err.message || 'getBars failed');
        });
    }

    subscribeBars(symbolInfo, resolution, onRealtimeCallback, subscriberUID, onResetCacheNeededCallback) {
      const symbol = normalizeSymbol(symbolInfo.ticker || symbolInfo.name || symbolInfo.symbol);
      const key = `${subscriberUID}:${symbol}:${resolution}`;

      if (this.subscriptions.has(key)) {
        clearInterval(this.subscriptions.get(key).timer);
      }

      const state = {
        symbol,
        resolution,
        lastBar: this.cache.get(symbol + ':' + resolution) || null,
        timer: null,
      };

      const poll = async () => {
        try {
          const seconds = resolutionToSeconds(resolution);
          const now = Math.floor(Date.now() / 1000);
          const from = Math.max(0, now - Math.max(seconds * 3, 7200));
          const data = await api('history', { symbol, resolution, from, to: now });
          const bars = (data.bars || []).map(makeBar);
          
          if (!bars.length) return;

          const last = bars[bars.length - 1];
          if (!state.lastBar) {
            state.lastBar = last;
            onRealtimeCallback(last);
            return;
          }

          if (last.time === state.lastBar.time) {
            state.lastBar = last;
            onRealtimeCallback(last);
            return;
          }

          if (last.time > state.lastBar.time) {
            state.lastBar = last;
            onRealtimeCallback(last);
            if (typeof onResetCacheNeededCallback === 'function') {
              onResetCacheNeededCallback();
            }
          }
        } catch (e) {}
      };

      state.timer = window.setInterval(poll, 15000);
      this.subscriptions.set(key, state);
      poll();
    }

    unsubscribeBars(subscriberUID) {
      for (const [key, value] of this.subscriptions.entries()) {
        if (key.startsWith(subscriberUID + ':')) {
          clearInterval(value.timer);
          this.subscriptions.delete(key);
        }
      }
    }

    getServerTime(callback) {
      api('server-time')
        .then((data) => callback(data.time || Math.floor(Date.now() / 1000)))
        .catch(() => callback(Math.floor(Date.now() / 1000)));
    }

    getQuotes(symbols, onDataCallback, onErrorCallback) {
      Promise.all(symbols.map((symbol) => api('quote', { symbol: normalizeSymbol(symbol) })))
        .then((results) => {
          onDataCallback(results.map((r) => ({
            s: 'ok',
            n: r.symbol,
            v: r.data,
          })));
        })
        .catch((err) => onErrorCallback(err.message || 'getQuotes failed'));
    }

    subscribeQuotes(symbols, fastSymbols, onRealtimeCallback, listenerGUID) {
      const timer = window.setInterval(async () => {
        try {
          const results = await Promise.all(symbols.map((symbol) => api('quote', { symbol: normalizeSymbol(symbol) })));
          onRealtimeCallback(results.map((r) => ({
            s: 'ok',
            n: r.symbol,
            v: r.data,
          })));
        } catch (e) {}
      }, 15000);

      this.subscriptions.set(`quotes:${listenerGUID}`, { timer });
    }

    unsubscribeQuotes(listenerGUID) {
      const key = `quotes:${listenerGUID}`;
      const sub = this.subscriptions.get(key);
      if (sub) {
        clearInterval(sub.timer);
        this.subscriptions.delete(key);
      }
    }
  }

  window.NobitexDatafeed = MultiExchangeDatafeed;

  function waitForTradingViewReady() {
    return new Promise((resolve) => {
      const tick = () => {
        if (window.TradingView && typeof window.TradingView.widget === 'function') resolve();
        else setTimeout(tick, 100);
      };
      tick();
    });
  }

  async function loadExchanges() {
    try {
      const exchangeSelect = document.getElementById('exchangeSelect');
      const response = await api('exchanges');
      const data = Array.isArray(response) ? response : (response.data || []);

      exchangeSelect.innerHTML = '';
      
      if (!data || data.length === 0) {
        exchangeSelect.innerHTML = '<option value="Nobitex">نوبیتکس</option>';
        config.exchange = 'Nobitex';
        return;
      }

      data.forEach(ex => {
        const opt = document.createElement('option');
        
        let enName = String(ex.translations?.en || ex.slug || 'Nobitex').trim();
        if(!enName || enName.toLowerCase() === 'undefined' || enName.toLowerCase() === 'null') {
            enName = 'Nobitex';
        }
        
        opt.value = enName;
        
        const faName = ex.translations?.fa || ex.slug || 'ناشناس';
        opt.textContent = `${faName} (${enName})`;
        
        if (enName.toLowerCase() === config.exchange.toLowerCase()) {
          opt.selected = true;
          config.exchange = enName;
        }
        
        exchangeSelect.appendChild(opt);
      });

      let selectedVal = String(exchangeSelect.value || '').trim();
      if (!selectedVal || selectedVal.toLowerCase() === 'undefined' || selectedVal.toLowerCase() === 'null') {
          selectedVal = 'Nobitex';
          exchangeSelect.value = 'Nobitex';
      }
      config.exchange = selectedVal;

    } catch (err) {
      config.exchange = 'Nobitex';
      const exchangeSelect = document.getElementById('exchangeSelect');
      if (exchangeSelect) {
        exchangeSelect.innerHTML = '<option value="Nobitex">نوبیتکس</option>';
        exchangeSelect.value = 'Nobitex';
      }
    }
  }

  async function init() {
    await waitForTradingViewReady();
    await loadExchanges();

    const datafeed = new MultiExchangeDatafeed();
    const searchInput = document.getElementById('symbolSearch');
    const symbolLabel = document.getElementById('symbolLabel');
    const exchangeSelect = document.getElementById('exchangeSelect');

    let widget = null;

    function mountChart(symbol) {
      if (widget && typeof widget.remove === 'function') {
        widget.remove();
      }

      const container = document.getElementById('tv_chart_container');
      container.innerHTML = '';

      widget = new TradingView.widget({
        container: 'tv_chart_container',
        library_path: window.NOBITEX_TV_LIBRARY_PATH || './static/charting_library/',
        datafeed,
        symbol,
        interval: config.defaultResolution,
        locale: 'fa',
        timezone: 'Asia/Tehran',
        autosize: true,
        fullscreen: false,
        debug: false,
        studies_overrides: {},
        disabled_features: [
          'header_screenshot',
          'header_compare',
          'study_templates'
        ],
        enabled_features: [],
        theme: 'light',
      });

      symbolLabel.textContent = symbol;
    }

    exchangeSelect.addEventListener('change', async (e) => {
      const selectedValue = e.target.value;
      
      if (selectedValue && selectedValue.toLowerCase() !== 'undefined') {
        config.exchange = selectedValue;
      } else {
        config.exchange = 'Nobitex';
      }

      const currentSym = normalizeSymbol(searchInput.value) || config.defaultSymbol;

      try {
        const res = await api('search', { query: '' });
        if (res.s === 'ok' && res.symbols && res.symbols.length > 0) {
          const exactMatch = res.symbols.find(s => s.symbol === currentSym);
          if (exactMatch) {
            mountChart(currentSym);
          } else {
            const baseCoin = currentSym.substring(0, 3);
            const similarMatch = res.symbols.find(s => s.symbol.startsWith(baseCoin));
            const nextSymbol = similarMatch ? similarMatch.symbol : res.symbols[0].symbol;

            searchInput.value = nextSymbol;
            mountChart(nextSymbol);
          }
        } else {
          mountChart(currentSym);
        }
      } catch (err) {
        mountChart(currentSym);
      }
    });

    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const next = normalizeSymbol(searchInput.value) || config.defaultSymbol;
        mountChart(next);
      }
    });

    mountChart(config.defaultSymbol);
  }

  document.addEventListener('DOMContentLoaded', () => {
    init().catch((err) => {
      const el = document.getElementById('status');
      if (el) el.textContent = err.message || String(err);
    });
  });
})();