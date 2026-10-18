const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const en = require('../../../frontend/messages/en.json');
(async () => {
 const browser = await chromium.launch({channel:'msedge',headless:true,args:['--use-angle=swiftshader','--enable-webgl','--ignore-gpu-blocklist']});
 const page = await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[], historyRequests=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(r.url().endsWith('/messages')) historyRequests.push(r.url());});
 await page.goto('http://localhost:3001/vi/scenes/demo?check=2',{waitUntil:'networkidle',timeout:90000});
 assert(page.url().includes('/en/scenes/demo?check=2'));
 await page.waitForSelector('canvas'); await page.waitForTimeout(1500);
 assert.equal(await page.locator('html').getAttribute('lang'),'en');
 assert.equal(await page.locator('.language-switch').count(),0);
 const original = await page.locator('canvas').screenshot();
 await page.getByRole('button',{name:'Instances',exact:true}).click();
 await page.waitForTimeout(250);
 const instances=await page.locator('canvas').screenshot(); assert(!original.equals(instances),'instance colors must change rendered pixels');
 await page.screenshot({path:__dirname+'/instances-points.png'});
 let pointPicked=false;
 for(let y=300;y<760&&!pointPicked;y+=25) for(let x=360;x<1050&&!pointPicked;x+=25) {
   await page.mouse.move(x,y); await page.waitForTimeout(20);
   if(await page.getByRole('tooltip').count()) { await page.mouse.click(x,y); pointPicked=true; }
 }
 assert(pointPicked,'real GPU picking must find an Object on the Point Cloud');
 await page.locator('.object-details').waitFor();
 await page.getByRole('button',{name:en.ui.close,exact:true}).click();
 await page.getByRole('button',{name:en.ui.resetView,exact:true}).click();
 await page.waitForTimeout(250);

 await page.getByRole('searchbox',{name:en.search}).fill('green');
 await page.getByRole('status',{name:en.heatmap.title}).waitFor();
 await page.screenshot({path:__dirname+'/heatmap-points.png'});
 await page.getByRole('button',{name:'Clear',exact:true}).click();
 assert.equal(await page.locator('.heatmap-legend').count(),0);
 assert.equal(await page.getByRole('button',{name:'Instances',exact:true}).getAttribute('aria-pressed'),'true');
 await page.getByRole('button',{name:en.layers.mesh,exact:true}).click();
 await page.waitForTimeout(1500);
 await page.screenshot({path:__dirname+'/instances-mesh.png'});
 let picked=false;
 for(let y=300;y<760&&!picked;y+=35) for(let x=360;x<1050&&!picked;x+=35) {
   await page.mouse.move(x,y); await page.waitForTimeout(20);
   if(await page.getByRole('tooltip').count()) { await page.mouse.click(x,y); picked=true; }
 }
 assert(picked,'real GPU picking must find an Object on the mesh');
 await page.locator('.object-details').waitFor();
 assert((await page.locator('.object-details').innerText()).includes('m'));
 await page.getByRole('button',{name:en.ui.close,exact:true}).click();
 await page.getByRole('button',{name:en.measure,exact:true}).click();
 await page.mouse.click(620,500); await page.mouse.click(700,560);
 await page.locator('.distance-value').waitFor({timeout:5000});
 await page.screenshot({path:__dirname+'/measurement-mesh.png'});
 await page.getByRole('button',{name:en.ui.exitMeasure,exact:true}).click();
 await page.getByRole('button',{name:en.ui.askScene,exact:true}).click();
 const input=page.getByRole('textbox',{name:en.question,exact:true});
 await input.fill('What is in this scene?'); await input.press('Enter');
 await page.locator('.message.assistant').waitFor();
 await page.waitForTimeout(350);
 await input.fill('Which object is highlighted?'); await input.press('Enter');
 await page.waitForTimeout(600);
 assert.equal(await page.locator('.message.user').count(),1);
 assert.equal(await page.locator('.message.assistant').count(),1);
 assert(!(await page.locator('.messages').innerText()).includes('What is in this scene?'));
 assert.equal(historyRequests.length,0);
 await page.screenshot({path:__dirname+'/independent-chat.png'});
 await page.getByRole('button',{name:en.inspector.title,exact:true}).click();
 const inspector=page.getByRole('complementary',{name:en.inspector.title});
 await inspector.getByRole('button',{name:en.inspector.stages.graph.title,exact:true}).click();
 assert((await inspector.innerText()).includes('graph.fake'));
 await inspector.getByRole('button',{name:en.inspector.stages.attributes.title,exact:true}).click();
 assert((await inspector.innerText()).includes(en.inspector.disabled));
 await page.screenshot({path:__dirname+'/inspector.png'});
 await page.getByRole('button',{name:en.ui.askScene,exact:true}).click();
 assert.equal(await page.locator('.message.assistant').count(),1,'latest answer survives Inspector and panel switching');
 assert((await page.locator('.messages').innerText()).includes('Which object is highlighted?'));

 await page.reload({waitUntil:'networkidle'}); await page.waitForSelector('canvas');
 await page.getByRole('button',{name:en.ui.askScene,exact:true}).click();
 assert.equal(await page.locator('.message').count(),0);
 assert.equal(historyRequests.length,0);
 assert.deepEqual(errors,[]);
 console.log('PASS: locale redirect, English navigation, rendered instance colors, heatmap, Clear, Point Cloud and Mesh GPU picking, manual measurement, latest-only QA without history fetch, answer retention across panel changes, Inspector metadata, empty chat after Scene reopen.');
 await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});