// Run with: node --test tools/tests/test_desktop_exports.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../../static/js/desktop.js'), 'utf8');

function setup({desktop=true, html=false, failed=false}={}) {
  const events={}, calls={saved:[], fetched:[], alerts:[], html:[]};
  const link={href:'http://127.0.0.1:1234/courses/',target:'_blank'};
  const window={addEventListener:(name, fn)=>{events[name]=fn},alert:msg=>calls.alerts.push(msg)};
  if (desktop) window.pywebview={api:{save_report:async (...args)=>{calls.saved.push(args);return {saved:true}}}};
  const document={addEventListener:(name,fn)=>{events[name]=fn},querySelectorAll:()=>[link],
    open:()=>{},write:text=>calls.html.push(text),close:()=>{}};
  class FormData { constructor(form) {this.values=[...form.fields]} append(...args) {this.values.push(args)} }
  class FileReader {readAsDataURL(blob) {this.result='data:application/octet-stream;base64,'+Buffer.from(blob).toString('base64');this.onload()} }
  vm.runInNewContext(source,{window,document,location:{href:'http://127.0.0.1:1234/reports/student-scores/',origin:'http://127.0.0.1:1234'},
    URL,FormData,FileReader,fetch:async (url,options)=>{
      calls.fetched.push({url:String(url),options});
      return {ok:!failed,status:failed?403:200,headers:{get:()=>html?'':'attachment; filename="student-scores.xlsx"'},
        text:async()=>'<html>Server validation errors</html>',blob:async()=>Buffer.from('original POST bytes')};
    }});
  const button={name:'action',value:'export',disabled:false};
  let prevented=false;
  const event={target:{action:'',fields:[['csrfmiddlewaretoken','example'],['modules','10'],['modules','11']]},submitter:button,
    preventDefault:()=>{prevented=true}};
  return {events,calls,button,event,link,prevented:()=>prevented};
}

test('desktop export preserves selected modules and POST response exactly once',async()=>{
  const context=setup();await context.events.submit(context.event);
  assert.equal(context.calls.fetched.length,1);
  const {options}=context.calls.fetched[0];assert.equal(options.method,'POST');
  assert.equal(JSON.stringify(options.body.values),JSON.stringify([
    ['csrfmiddlewaretoken','example'],['modules','10'],['modules','11'],['action','export']]));
  assert.equal(context.calls.saved[0][0],'student-scores.xlsx');
  assert.equal(Buffer.from(context.calls.saved[0][1],'base64').toString(),'original POST bytes');
  assert.equal(context.button.disabled,false);assert.equal(context.link.target,'_self');
});
test('browser exports retain ordinary form submission',async()=>{
  const context=setup({desktop:false});await context.events.submit(context.event);
  assert.equal(context.prevented(),false);assert.equal(context.calls.fetched.length,0);
  assert.equal(context.link.target,'_blank');
});
test('preview buttons retain ordinary form submission',async()=>{
  const context=setup();context.button.value='preview';await context.events.submit(context.event);
  assert.equal(context.prevented(),false);assert.equal(context.calls.fetched.length,0);
});
test('validation HTML is displayed without retrying the export',async()=>{
  const context=setup({html:true});await context.events.submit(context.event);
  assert.equal(context.calls.saved.length,0);assert.equal(context.calls.fetched.length,1);
  assert.deepEqual(context.calls.html,['<html>Server validation errors</html>']);
});
test('failed export leaves the button usable and does not save an error page',async()=>{
  const context=setup({failed:true});await context.events.submit(context.event);
  assert.equal(context.calls.saved.length,0);assert.equal(context.button.disabled,false);
  assert.equal(context.calls.alerts.length,1);
});
