// ═══════════════════════════════════════════════════════════════
// Српски Фудбал — Cloudflare Worker
// Руте: /tabela /rezultati /uzivo /raspored /seasons /img
// ═══════════════════════════════════════════════════════════════

const SOFA_BASE = 'https://www.sofascore.com/api/v1';
const TID = 210; // Superliga Srbije

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS, 'Content-Type': 'application/json;charset=UTF-8', 'Cache-Control': 'public,max-age=60' },
  });
}

function err(msg, status = 500) {
  return new Response(JSON.stringify({ error: msg }), {
    status,
    headers: { ...CORS, 'Content-Type': 'application/json' },
  });
}

async function sofaFetch(path) {
  const r = await fetch(SOFA_BASE + path, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      'Referer': 'https://www.sofascore.com/',
    },
    cf: { cacheTtl: 60, cacheEverything: true },
  });
  if (!r.ok) throw new Error('Sofa HTTP ' + r.status);
  return r.json();
}

// ── /img — proxy slike (zaobilazi hotlink zaštitu) ──────────────
async function handleImg(url) {
  if (!url) return new Response('Missing url param', { status: 400, headers: CORS });

  try {
    const r = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': new URL(url).origin + '/',
        'Accept': 'image/webp,image/avif,image/*,*/*',
      },
      cf: { cacheTtl: 3600, cacheEverything: true },
    });
    if (!r.ok) throw new Error('Image HTTP ' + r.status);

    const contentType = r.headers.get('content-type') || 'image/jpeg';
    const body = await r.arrayBuffer();
    return new Response(body, {
      status: 200,
      headers: {
        ...CORS,
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=3600',
      },
    });
  } catch (e) {
    return new Response('Image error: ' + e.message, { status: 502, headers: CORS });
  }
}

// ── /tabela ─────────────────────────────────────────────────────
async function handleTabela(sid) {
  const d = await sofaFetch(`/unique-tournament/${TID}/season/${sid}/standings/total`);
  const rows = d.standings?.[0]?.rows || [];
  return json({
    tabela: rows.map(r => ({
      poz: r.position,
      klub: r.team?.name || '',
      u: r.matches, p: r.wins, n: r.draws, i: r.losses,
      gd: r.scoreDiffFormatted || `${r.scoresFor}-${r.scoresAgainst}`,
      go: `${r.scoresFor}:${r.scoresAgainst}`,
      bod: r.points,
      forma: (r.team?.form || '').split('').map(f => f === 'W' ? 'П' : f === 'D' ? 'Н' : f === 'L' ? 'И' : f).join(''),
    })),
  });
}

// ── /rezultati ──────────────────────────────────────────────────
async function handleRezultati(sid) {
  const d = await sofaFetch(`/unique-tournament/${TID}/season/${sid}/events/last/0`);
  const evs = d.events || [];
  const byRound = {};
  evs.forEach(e => { const k = e.roundInfo?.round || 0; (byRound[k] = byRound[k] || []).push(e); });
  const lastRound = Math.max(...Object.keys(byRound).map(Number));
  return json({
    zadnje: {
      kolo: lastRound,
      utakmice: (byRound[lastRound] || []).map(e => ({
        id: e.id,
        domacin: e.homeTeam?.name, gost: e.awayTeam?.name,
        golD: e.homeScore?.current ?? null, golG: e.awayScore?.current ?? null,
        statusTip: e.status?.type, minut: e.time?.played || null,
      })),
    },
  });
}

// ── /uzivo ──────────────────────────────────────────────────────
async function handleUzivo() {
  const d = await sofaFetch('/sport/football/events/live');
  const live = (d.events || []).filter(e => e.tournament?.uniqueTournament?.id === TID);
  return json({
    uzivo: live.map(e => ({
      domacin: e.homeTeam?.name, gost: e.awayTeam?.name,
      golD: e.homeScore?.current ?? null, golG: e.awayScore?.current ?? null,
      minut: e.time?.played || null,
    })),
  });
}

// ── /raspored ───────────────────────────────────────────────────
async function handleRaspored(sid) {
  const d = await sofaFetch(`/unique-tournament/${TID}/season/${sid}/events/next/0`);
  return json({
    sledece: (d.events || []).slice(0, 8).map(e => ({
      id: e.id,
      kolo: e.roundInfo?.round,
      domacin: e.homeTeam?.name, gost: e.awayTeam?.name,
      timestamp: e.startTimestamp,
    })),
  });
}

// ── /seasons ────────────────────────────────────────────────────
async function handleSeasons() {
  const d = await sofaFetch(`/unique-tournament/${TID}/seasons`);
  return json({ seasons: d.seasons || [] });
}

// ── Main handler ────────────────────────────────────────────────
export default {
  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS });
    }

    try {
      // Image proxy — no season needed
      if (path === '/img') {
        return handleImg(url.searchParams.get('url'));
      }

      // All other routes need season ID
      const sidParam = url.searchParams.get('sid');
      let sid = sidParam;

      if (!sid && path !== '/seasons') {
        // Auto-detect current season
        const s = await sofaFetch(`/unique-tournament/${TID}/seasons`);
        sid = s.seasons?.[0]?.id;
        if (!sid) return err('Cannot detect season ID');
      }

      if (path === '/tabela')    return handleTabela(sid);
      if (path === '/rezultati') return handleRezultati(sid);
      if (path === '/uzivo')     return handleUzivo();
      if (path === '/raspored')  return handleRaspored(sid);
      if (path === '/seasons')   return handleSeasons();

      return new Response('Not found', { status: 404, headers: CORS });
    } catch (e) {
      return err(e.message);
    }
  },
};
