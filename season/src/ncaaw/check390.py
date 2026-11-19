"""390 px phone check: every tab's scroll width must equal 390. Usage: python3 check390.py out/M/index.html"""
import sys, asyncio, pathlib
from playwright.async_api import async_playwright
async def main(p):
    html = pathlib.Path(p).read_text()
    if 'name="viewport"' not in html: html = '<meta name="viewport" content="width=device-width,initial-scale=1">' + html
    tmp = pathlib.Path(p).with_name('_check.html'); tmp.write_text(html)
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); pg = await b.new_page(viewport={'width': 390, 'height': 844})
        await pg.goto('file://' + str(tmp.resolve())); bad = []
        tabs = await pg.eval_on_selector_all('.tab', 'els => els.map(e => e.dataset.tab)')
        for t in tabs:
            await pg.click(f".tab[data-tab='{t}']")
            await pg.evaluate("document.querySelectorAll('details').forEach(d=>d.open=true)")
            w = await pg.evaluate('document.documentElement.scrollWidth')
            print(f'{t}: {w}'); bad += [t] if w != 390 else []
        await pg.set_viewport_size({'width': 1280, 'height': 900}); await pg.emulate_media(color_scheme='dark')
        await pg.click(".tab[data-tab='slate']"); await pg.screenshot(path=str(pathlib.Path(p).with_name('desktop_dark.png')))
        await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.emulate_media(color_scheme='light')
        await pg.evaluate("document.querySelectorAll('details').forEach(d=>d.open=false)"); await pg.screenshot(path=str(pathlib.Path(p).with_name('phone.png')))
        await b.close(); tmp.unlink()
    print('FAIL' if bad else 'PASS', bad)
asyncio.run(main(sys.argv[1]))
