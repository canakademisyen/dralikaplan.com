# dralikaplan.com — nasıl çalışır?

Site her **pazartesi 07:00**'de GitHub Actions tarafından kendiliğinden güncellenir
(`.github/workflows/update-site.yml`). Beklemek istemezseniz GitHub'da
**Actions → Update site → Run workflow** ile hemen çalıştırabilirsiniz (telefondan da olur).

Her çalıştırmada sırasıyla:

| Adım | Kaynak | Sonuç |
|---|---|---|
| `fetch_avesis.py` | Avesis profiliniz | Projects ve Teaching |
| `fetch_publications.py` | ORCID, OpenAlex, Crossref, Google Scholar (SerpApi) | Research Papers, Books, atıflar |
| `build_site.py` | `content/` klasörü | `dist/` (yayınlanan site) |

Yani yeni bir makaleyi **ORCID**'e, yeni bir proje ya da dersi **Avesis**'e girmeniz yeterli.

## Klasörler

- `content/` — veriler ve ayarlar (aşağıda)
- `static/` — sitede olduğu gibi yayınlanan dosyalar (profil fotoğrafı)
- `tools/` — betikler
- `dist/` — üretilen site (elle düzenlemeyin; her derlemede yeniden oluşur)

## Elle düzenleyebileceğiniz dosyalar (`content/`)

- `translations.json` — Avesis Türkçe olduğu için İngilizce başlık/açıklamalar burada.
  Avesis'e yeni bir proje veya ders eklerseniz, çeviri eklenene kadar sitede Türkçe görünür;
  GitHub'daki çalıştırma kaydı hangi başlığın çeviri beklediğini yazar.
- `publications-config.json` — ORCID, Scholar kimliği, çıkarılacak yayınlar (`exclude_dois`,
  `exclude_openalex_ids`), anahtar kelime ayarları (`keywords`: hide / merge / add / max_per_paper).
- `projects.json`, `teaching.json`, `publications.json` — **otomatik üretilir**, elle değiştirmeyin.
- `secrets.json` — yalnızca bu bilgisayarda; GitHub'a gönderilmez. GitHub'da anahtar
  **Settings → Secrets and variables → Actions → `SERPAPI_KEY`** olarak durur.

## Bilgisayarda denemek (isteğe bağlı)

```bash
python3 tools/fetch_avesis.py && python3 tools/fetch_publications.py && python3 tools/build_site.py
```

```bash
python3 tools/serve.py
```

Sonra tarayıcıda http://localhost:8791 adresini açın.
