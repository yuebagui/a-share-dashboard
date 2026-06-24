(() => {
  const SEARCH_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8";
  let requestId = 0;

  async function score(input, mode = "auto") {
    const stock = await resolveStock(input);
    const [quote, bars] = await Promise.all([
      fetchTencentQuote(stock.prefix, stock.code),
      fetchTencentBars(stock.prefix, stock.code),
    ]);
    return { ok: true, ...scoreAnalysis(quote, bars, mode), kline_source: "tencent" };
  }

  async function resolveStock(input) {
    const text = String(input || "").trim();
    const codeMatch = text.toLowerCase().match(/^(sh|sz)?\s*(\d{6})$/);
    if (codeMatch) {
      const code = codeMatch[2];
      return { code, prefix: codeMatch[1] || inferPrefix(code) };
    }
    const payload = await loadJsonp(
      `https://searchapi.eastmoney.com/api/suggest/get?input=${encodeURIComponent(text)}&type=14&count=8&token=${SEARCH_TOKEN}`,
      "cb",
    );
    const items = payload?.QuotationCodeTable?.Data || [];
    const item = items.find((candidate) => candidate.Classify === "AStock" && /^\d{6}$/.test(candidate.Code));
    if (!item) throw new Error(`未找到A股股票：${text}`);
    return { code: item.Code, prefix: item.MktNum === "1" ? "sh" : "sz" };
  }

  function inferPrefix(code) {
    return code.startsWith("5") || code.startsWith("6") || code.startsWith("9") ? "sh" : "sz";
  }

  async function fetchTencentQuote(prefix, code) {
    const variable = `v_${prefix}${code}`;
    await loadScript(`https://qt.gtimg.cn/q=${prefix}${code}`, variable, "gbk");
    const text = window[variable];
    delete window[variable];
    const parts = String(text || "").split("~");
    if (parts.length < 35 || !parts[3]) throw new Error("实时行情返回不完整");
    return {
      code,
      market: prefix,
      name: parts[1],
      price: number(parts[3]),
      change_pct: number(parts[32]),
      open: number(parts[5]),
      high: number(parts[33]),
      low: number(parts[34]),
      prev_close: number(parts[4]),
      volume: number(parts[6]) * 100,
      amount: number(parts[37]) * 10000,
      time: parts[30] || "",
      source: "tencent",
    };
  }

  async function fetchTencentBars(prefix, code) {
    const variable = `__publicKline${Date.now()}${requestId++}`;
    const url = `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${prefix}${code},day,,,160,qfq&_var=${variable}`;
    await loadScript(url, variable);
    const payload = window[variable];
    delete window[variable];
    const item = Object.values(payload?.data || {})[0] || {};
    const rows = item.qfqday || item.day || [];
    const bars = rows
      .filter((row) => row.length >= 6)
      .map((row) => ({
        date: row[0],
        open: number(row[1]),
        close: number(row[2]),
        high: number(row[3]),
        low: number(row[4]),
        volume: number(row[5]),
      }));
    if (bars.length < 60) throw new Error(`历史K线不足：${bars.length}条`);
    return bars;
  }

  function loadJsonp(baseUrl, callbackParam) {
    const callback = `__publicJsonp${Date.now()}${requestId++}`;
    return new Promise((resolve, reject) => {
      const timer = window.setTimeout(() => cleanup(new Error("名称搜索超时")), 12000);
      const script = document.createElement("script");
      const separator = baseUrl.includes("?") ? "&" : "?";
      script.src = `${baseUrl}${separator}${callbackParam}=${callback}`;
      script.onerror = () => cleanup(new Error("名称搜索失败"));
      window[callback] = (payload) => cleanup(null, payload);
      document.head.appendChild(script);

      function cleanup(error, payload) {
        window.clearTimeout(timer);
        script.remove();
        delete window[callback];
        if (error) reject(error);
        else resolve(payload);
      }
    });
  }

  function loadScript(url, expectedGlobal, charset = "utf-8") {
    return new Promise((resolve, reject) => {
      const timer = window.setTimeout(() => cleanup(new Error("行情请求超时")), 12000);
      const script = document.createElement("script");
      script.src = url;
      script.charset = charset;
      script.onload = () => {
        if (window[expectedGlobal] == null) cleanup(new Error("行情数据为空"));
        else cleanup();
      };
      script.onerror = () => cleanup(new Error("行情请求失败"));
      document.head.appendChild(script);

      function cleanup(error) {
        window.clearTimeout(timer);
        script.remove();
        if (error) reject(error);
        else resolve();
      }
    });
  }

  function scoreAnalysis(quote, bars, mode) {
    const closes = bars.map((bar) => bar.close);
    const highs = bars.map((bar) => bar.high);
    const lows = bars.map((bar) => bar.low);
    const volumes = bars.map((bar) => bar.volume);
    const last = bars.at(-1);
    const price = quote.price || last.close;
    const ma20 = sma(closes, 20) || last.close;
    const ma60 = sma(closes, 60);
    const ma20Prev5 = closes.length >= 25 ? mean(closes.slice(-25, -5)) : ma20;
    const atrs = atrValues(bars);
    const atr = atrs.at(-1);
    const atrPct = (atr / price) * 100;
    const high60 = Math.max(...highs.slice(-60));
    const low60 = Math.min(...lows.slice(-60));
    const position60 = high60 > low60 ? ((price - low60) / (high60 - low60)) * 100 : 50;
    const avg20Volume = sma(volumes, 20) || last.volume;
    const volumeRatio = avg20Volume ? last.volume / avg20Volume : 1;
    const change5 = closes.length >= 6 ? (price / closes.at(-6) - 1) * 100 : 0;
    const averageRange = Math.max(mean(bars.slice(-10).map((bar) => ((bar.high - bar.low) / bar.close) * 100)), 0.1);
    const gainSafety = change5 / averageRange;
    const ema12 = emaSeries(closes, 12);
    const ema26 = emaSeries(closes, 26);
    const dif = ema12.map((value, index) => value - ema26[index]);
    const dea = emaSeries(dif, 9);
    const macdNow = dif.at(-1) - dea.at(-1);
    const macdPrev = dif.at(-2) - dea.at(-2);
    const codeType = classifyCode(quote.market, quote.code);
    const ratio = price / ma20;
    let trendScore = ratio >= 1.08 ? 15 : ratio >= 1.05 ? 13 : ratio >= 1.03 ? 11 : ratio >= 1 ? 8 : ratio >= 0.97 ? 5 : ratio >= 0.95 ? 2 : 0;
    const slope = (ma20 / ma20Prev5 - 1) * 100;
    trendScore += slope >= 1.5 ? 10 : slope >= 0.8 ? 8 : slope >= 0.3 ? 6 : slope >= 0 ? 4 : slope >= -0.5 ? 2 : 0;
    const macdScore = macdNow > 0 && macdNow > macdPrev ? 10 : macdNow > 0 ? 7 : macdNow > macdPrev ? 5 : 0;
    const positionScore = position60 < 30 ? 10 : position60 < 50 ? 8 : position60 < 70 ? 6 : position60 < 85 ? 3 : 0;
    const atrScore = atrPct < 3 ? 10 : atrPct < 4 ? 8 : atrPct < 5 ? 6 : atrPct < 6 ? 4 : atrPct < 7 ? 2 : 0;
    const volatilityScore = atrScore + (atr < mean(atrs.slice(-10)) ? 5 : 2);
    const [volumePriceScore, volumeLabel] = volumePrice(last, volumeRatio, price, ma20);
    const pullbackScore = pullbackQuality(bars, avg20Volume);
    const [buyFitScore, buyFitLabel] = buyPointFit(price, last, ma20, high60, position60, volumeRatio, mode, codeType);
    const [riskScore, riskLabel, stopReference] = riskAssessment(price, ma20, atr, low60, last.low, mode);
    const modeScore = modeFit(mode, codeType, price, ma20, volumeRatio, position60, last);
    const safetyScore = gainSafety < 0.7 ? 5 : gainSafety < 1 ? 3 : gainSafety < 1.3 ? 1 : 0;
    const total = Math.round(clamp(trendScore + macdScore + positionScore + volatilityScore + volumePriceScore + pullbackScore + buyFitScore + riskScore + modeScore + safetyScore, 0, 100));
    const vetoes = detectVetoes(price, last, ma20, volumeRatio, atrPct, position60);
    return {
      quote,
      bar_source_date: last.date,
      technical: {
        ma20: round(ma20, 3),
        ma60: ma60 ? round(ma60, 3) : null,
        ma20_slope_5d_pct: round(slope, 2),
        atr: round(atr, 3),
        atr_pct: round(atrPct, 2),
        high60: round(high60, 3),
        low60: round(low60, 3),
        position_60_pct: round(position60, 1),
        volume_ratio: round(volumeRatio, 2),
        macd_hist: round(macdNow, 4),
        code_type: codeType,
        stop_reference: stopReference,
      },
      score: {
        total,
        trend: trendScore,
        macd: macdScore,
        position: positionScore,
        volatility: volatilityScore,
        volume_price: volumePriceScore,
        pullback: pullbackScore,
        buy_point_fit: buyFitScore,
        risk: riskScore,
        mode_fit: modeScore,
        gain_safety: safetyScore,
      },
      labels: {
        volume_price: volumeLabel,
        buy_point: buyFitLabel,
        risk: riskLabel,
        mode: bestModeLabel(mode, codeType, price, ma20, volumeRatio, position60),
      },
      vetoes,
      action: vetoes.length ? "回避/等待修复" : total >= 90 ? "重点观察，触发计划后可参与" : total >= 80 ? "标准候选，按计划买点参与" : total >= 70 ? "小仓试错或继续观察" : "暂不参与",
      confidence: !vetoes.length && total >= 70 ? (total >= 80 ? "中高" : "中") : "偏低",
      suggested_position: suggestPosition(total, vetoes, riskLabel),
      plan: buildPlan(total, vetoes, price, ma20, atr, high60, low60, last, mode),
      caveat: "自动分数主要来自股价、K线、量价和风险；主线题材、龙头地位、市场情绪需要结合当日复盘确认。",
    };
  }

  function volumePrice(last, volumeRatio, price, ma20) {
    const bodyPct = ((last.close - last.open) / Math.max(last.open, 0.01)) * 100;
    const upperShadow = ((last.high - Math.max(last.open, last.close)) / Math.max(last.close, 0.01)) * 100;
    const closePosition = (last.close - last.low) / Math.max(last.high - last.low, 0.01);
    if (bodyPct > 2 && volumeRatio >= 1.2 && closePosition > 0.65) return [15, "放量上涨，需求占优"];
    if (price >= ma20 && volumeRatio >= 0.5 && volumeRatio <= 1.2 && closePosition > 0.45) return [12, "量价健康，承接正常"];
    if (bodyPct < -2 && volumeRatio >= 1.2) return [3, "放量下跌，供应进场"];
    if (upperShadow > 3 && volumeRatio >= 1.4) return [0, "放量长上影，疑似滞涨"];
    if (volumeRatio < 0.6 && Math.abs(bodyPct) < 1.5) return [8, "缩量整理，等待方向"];
    return [7, "量价中性"];
  }

  function pullbackQuality(bars, averageVolume) {
    const recent = bars.slice(-3);
    if (recent.every((bar) => bar.close <= bar.open) && mean(recent.map((bar) => bar.volume)) < averageVolume * 0.8) return 10;
    if (recent.some((bar) => bar.close < bar.open && bar.volume > averageVolume * 1.2)) return 0;
    return 5;
  }

  function buyPointFit(price, last, ma20, high60, position60, volumeRatio, mode, codeType) {
    const nearMa20 = Math.abs(price / ma20 - 1) <= 0.035;
    const recovered = last.close > Math.max(last.open, (last.high + last.low) / 2);
    if ((mode === "20cm" || (mode === "auto" && codeType === "20cm")) && nearMa20 && recovered) return [10, "20cm分歧后靠近支撑并修复"];
    if ((mode === "20cm" || (mode === "auto" && codeType === "20cm")) && recovered && volumeRatio >= 1.1) return [8, "20cm反包修复迹象"];
    if ((mode === "trend" || mode === "auto") && price >= high60 * 0.97 && volumeRatio >= 1.2 && price > ma20) return [10, "容量趋势放量突破"];
    if ((mode === "trend" || mode === "auto") && nearMa20 && price > ma20) return [8, "趋势回踩MA20附近"];
    if (mode === "leader" && recovered && position60 < 85) return [8, "龙头分歧承接尚可"];
    return position60 >= 85 ? [2, "位置偏高，追高性价比低"] : [5, "买点一般，等待更明确触发"];
  }

  function riskAssessment(price, ma20, atr, low60, dayLow, mode) {
    const candidates = [price - 2 * atr, dayLow * 0.99, low60 * 0.995];
    if ((mode === "trend" || mode === "auto") && ma20 < price) candidates.push(ma20 * 0.985);
    const valid = candidates.filter((value) => value > 0 && value < price);
    const stop = valid.length ? Math.max(...valid) : price * 0.95;
    const distance = ((price - stop) / price) * 100;
    const reference = { technical_stop: round(stop, 3), stop_loss_pct: round(distance, 2) };
    if (distance <= 3) return [10, "止损距离舒适", reference];
    if (distance <= 5) return [7, "止损距离可接受", reference];
    if (distance <= 8) return [3, "止损偏远，需降仓或等回落", reference];
    return [0, "止损过远，不适合追入", reference];
  }

  function modeFit(mode, codeType, price, ma20, volumeRatio, position60, last) {
    if (mode === "20cm") return codeType === "20cm" ? 5 : 1;
    if (mode === "leader") return volumeRatio >= 1 && position60 < 85 ? 5 : 3;
    if (mode === "trend") return price > ma20 && volumeRatio >= 0.8 ? 5 : 2;
    if (codeType === "20cm" && last.close >= last.open) return 5;
    return price > ma20 ? 4 : 2;
  }

  function detectVetoes(price, last, ma20, volumeRatio, atrPct, position60) {
    const vetoes = [];
    const upperShadow = ((last.high - Math.max(last.open, last.close)) / Math.max(last.close, 0.01)) * 100;
    if (price < ma20 * 0.97) vetoes.push("价格明显跌破MA20，趋势未修复");
    if (upperShadow > 4 && volumeRatio > 1.4 && position60 > 70) vetoes.push("高位放量长上影，疑似滞涨");
    if (atrPct > 8) vetoes.push("ATR波动过高，止损难控制");
    if (last.close < last.open && volumeRatio > 1.5) vetoes.push("放量阴线，供应压力偏大");
    return vetoes;
  }

  function classifyCode(market, code) {
    if (/^(300|301|688|689)/.test(code)) return "20cm";
    if (/^(600|601|603|605|000|001|002|003)/.test(code)) return "10cm";
    if (/^(5|15|16|18)/.test(code)) return "etf";
    return market;
  }

  function bestModeLabel(mode, codeType, price, ma20, volumeRatio, position60) {
    if (mode !== "auto") return mode;
    if (codeType === "20cm" && position60 < 85) return "20cm反包/分歧低吸";
    if (price > ma20 && volumeRatio >= 1.1) return "容量趋势突破";
    return "龙头分歧低吸或等待确认";
  }

  function suggestPosition(total, vetoes, riskLabel) {
    if (vetoes.length || total < 70) return "0%-10%";
    if (riskLabel.includes("偏远") || riskLabel.includes("过远")) return "10%-15%";
    if (total >= 90) return "25%-50%，需市场强/中且为主线核心";
    if (total >= 80) return "25%-35%";
    return "10%-25%";
  }

  function buildPlan(total, vetoes, price, ma20, atr, high60, low60, last, mode) {
    const candidates = [price - 2 * atr, last.low * 0.99, low60 * 0.995];
    if (ma20 < price) candidates.push(ma20 * 0.985);
    const valid = candidates.filter((value) => value > 0 && value < price);
    const stop = valid.length ? Math.max(...valid) : price * 0.95;
    const buy = vetoes.length || total < 70
      ? "不主动买；等待站回MA20、量价转强、重新出现标准买点。"
      : mode === "20cm"
        ? "只做低吸修复：急杀后收回分时均线/关键支撑再试，不追高。"
        : mode === "trend"
          ? "放量突破平台或缩量回踩突破位/MA20不破再参与。"
          : "优先等分歧低吸或突破确认，避免一致加速时追入。";
    return {
      buy,
      stop: `参考止损 ${stop.toFixed(2)}；若亏损接近5%或跌破关键位不收回，执行硬止损。`,
      take_profit: "主线仍强且量价健康则持有；放量滞涨、长上影、板块退潮时减仓或离场。",
      levels: `MA20 ${ma20.toFixed(2)}，60日区间 ${low60.toFixed(2)}-${high60.toFixed(2)}，今日低点 ${last.low.toFixed(2)}。`,
    };
  }

  function atrValues(bars, period = 14) {
    const ranges = bars.map((bar, index) => {
      const previous = bars[index - 1]?.close;
      return previous == null ? bar.high - bar.low : Math.max(bar.high - bar.low, Math.abs(bar.high - previous), Math.abs(bar.low - previous));
    });
    return ranges.map((_, index) => mean(ranges.slice(Math.max(0, index + 1 - period), index + 1)));
  }

  function emaSeries(values, period) {
    const alpha = 2 / (period + 1);
    const output = [values[0]];
    for (const value of values.slice(1)) output.push(alpha * value + (1 - alpha) * output.at(-1));
    return output;
  }

  function sma(values, period) {
    return values.length >= period ? mean(values.slice(-period)) : null;
  }

  function mean(values) {
    return values.reduce((sum, value) => sum + value, 0) / Math.max(values.length, 1);
  }

  function number(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function round(value, digits) {
    return Number(value.toFixed(digits));
  }

  function clamp(value, low, high) {
    return Math.max(low, Math.min(high, value));
  }

  window.PublicStockCalculator = { score };
})();
