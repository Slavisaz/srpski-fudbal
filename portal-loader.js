/**
 * srpskifudbal.com — Portal data loader
 * Čita public/data/football.json i prikazuje vesti + prognoza dana
 * Bez ikakvih API ključeva — samo čita statički JSON
 */

const DATA_URL = '/data/football.json';

// ── Učitaj sve podatke ──────────────────────────────
async function ucitajPodatke() {
  try {
    const res = await fetch(DATA_URL + '?t=' + Date.now());
    if (!res.ok) throw new Error('Ne mogu da učitam podatke');
    return await res.json();
  } catch (e) {
    console.warn('Koristim demo podatke:', e.message);
    return null;
  }
}

// ── Prikaži vesti ───────────────────────────────────
function prikaziVesti(vesti) {
  const kontejner = document.getElementById('vesti-grid');
  if (!kontejner || !vesti?.length) return;

  kontejner.innerHTML = vesti.slice(0, 6).map(v => `
    <div class="nc" onclick="window.open('${v.url}','_blank')" style="cursor:pointer">
      <div class="nc-img" style="background:var(--off2);height:150px;overflow:hidden;display:flex;align-items:center;justify-content:center">
        ${v.slika
          ? `<img src="${v.slika}" alt="${v.naslov}" style="width:100%;height:150px;object-fit:cover">`
          : `<svg viewBox="0 0 360 150" width="100%" height="150"><rect width="360" height="150" fill="#e8f0fb"/><text x="180" y="90" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#9ca3af">${v.izvor}</text></svg>`
        }
      </div>
      <div class="nc-body">
        <div class="nc-cat">${v.izvor}</div>
        <div class="nc-ttl">${v.naslov}</div>
        <div class="nc-blrb">${v.opis ? v.opis.substring(0, 140) + '...' : ''}</div>
        <div class="nc-meta">
          <span>${v.datum}</span>
          <span>Прочитај →</span>
        </div>
      </div>
    </div>
  `).join('');
}

// ── Prikaži prognoza dana ───────────────────────────
function prikaziPrognoza(prognoza) {
  const kontejner = document.getElementById('prognoza-tiket');
  if (!kontejner || !prognoza) return;

  const zvezdicice = (n) => '★'.repeat(n) + '☆'.repeat(5 - n);

  kontejner.innerHTML = `
    <div style="background:var(--off);border:1px solid var(--bdr);border-radius:5px;padding:14px;margin-bottom:12px">
      <div style="font-family:var(--fd);font-size:12px;font-weight:700;color:var(--txt3);text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px">
        📅 Прогноза за ${prognoza.datum}
      </div>

      ${prognoza.utakmice.map(u => `
        <div style="background:white;border:1.5px solid var(--bdr);border-radius:4px;padding:10px 12px;margin-bottom:8px">
          <div style="font-family:var(--fd);font-size:11px;font-weight:600;color:var(--txt3);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">
            ${u.liga} · ${u.datum} ${u.vreme}
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:5px">
            <div style="font-family:var(--fd);font-size:15px;font-weight:700;color:var(--txt)">
              ${u.domacin} — ${u.gost}
            </div>
            <div style="display:flex;gap:6px;align-items:center;flex-shrink:0">
              <span style="background:var(--blue);color:white;font-family:var(--fd);font-size:13px;font-weight:800;padding:4px 10px;border-radius:3px">
                ${u.tip}
              </span>
              <span style="font-family:var(--fd);font-size:16px;font-weight:800;color:var(--red)">
                ${u.kvota.toFixed(2)}
              </span>
            </div>
          </div>
          <div style="font-family:var(--fu);font-size:12px;color:var(--txt3);margin-bottom:4px">
            ${u.analiza}
          </div>
          <div style="font-size:11px;color:var(--gold)">
            ${zvezdicice(u.pouzdanost)} Поузданост
          </div>
        </div>
      `).join('')}

      <!-- Ukupna kvota -->
      <div style="background:var(--blue);border-radius:4px;padding:12px 14px;display:flex;align-items:center;justify-content:space-between;margin-top:4px">
        <div>
          <div style="font-family:var(--fd);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:rgba(255,255,255,.65)">Укупна квота</div>
          <div style="font-family:var(--fd);font-size:28px;font-weight:800;color:var(--gold);line-height:1">${prognoza.ukupna_kvota.toFixed(2)}x</div>
        </div>
        <div style="text-align:right">
          <div style="font-family:var(--fu);font-size:11px;color:rgba(255,255,255,.55)">Пример (1.000 РСД)</div>
          <div style="font-family:var(--fd);font-size:20px;font-weight:800;color:white">${prognoza.dobitak_primer.toLocaleString('sr-RS')} РСД</div>
        </div>
      </div>

      <div style="font-family:var(--fu);font-size:10px;color:var(--txt4);text-align:center;margin-top:10px;line-height:1.5">
        ⚠ ${prognoza.napomena}
      </div>
    </div>
  `;
}

// ── Prikaži timestamp ažuriranja ─────────────────────
function prikaziAzurirano(azurirano_sr) {
  const el = document.getElementById('poslednje-azuriranje');
  if (el && azurirano_sr) el.textContent = 'Ажурирано: ' + azurirano_sr;
}

// ── Init ─────────────────────────────────────────────
async function init() {
  const podaci = await ucitajPodatke();
  if (!podaci) return;

  prikaziVesti(podaci.vesti);
  prikaziPrognoza(podaci.prognoza_dana);
  prikaziAzurirano(podaci.azurirano_sr);

  // Auto-refresh svakih 15 minuta
  setTimeout(init, 15 * 60 * 1000);
}

document.addEventListener('DOMContentLoaded', init);
