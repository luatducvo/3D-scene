const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const en=require('../../../frontend/messages/en.json');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true,args:['--use-angle=swiftshader','--ignore-gpu-blocklist']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.goto('http://localhost:3001/en/scenes/demo',{waitUntil:'networkidle'}); await page.waitForSelector('canvas');
 await page.evaluate(()=>{ const fetchNow=window.fetch; window.fetch=async (...args)=>{
  const response=await fetchNow(...args); const url=typeof args[0]==='string'?args[0]:args[0].url;
  if(url?.includes('/search')) await new Promise(resolve=>setTimeout(resolve,1200));
  return response;
 }; });
 await page.getByRole('searchbox',{name:en.search}).fill('green'); await page.waitForTimeout(450);
 await page.getByRole('button',{name:en.ui.askScene,exact:true}).click();
 await page.getByRole('textbox',{name:en.question}).fill('Where is the sofa?');
 await page.getByRole('textbox',{name:en.question}).press('Enter');
 await page.locator('.message.assistant').waitFor(); await page.waitForTimeout(1400);
 assert.equal(await page.locator('.heatmap-legend').count(),0,'stale search must not replace QA');
 assert(!(await page.locator('.search-status').innerText()).includes(en.ui.searching),'superseded search must stop saying Searching');
 await page.getByRole('button',{name:en.ui.close,exact:true}).click();
 await page.getByRole('searchbox',{name:en.search}).fill('sofa');
 await page.waitForTimeout(450);
 await page.getByRole('button',{name:'Clear',exact:true}).click();
 await page.waitForTimeout(1400);
 assert.equal(await page.locator('.heatmap-legend').count(),0,'Clear must invalidate pending responses');
 console.log('PASS: delayed search cannot replace QA or remain stuck loading; Clear invalidates old visualization.');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});