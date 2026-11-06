/** 浏览器本地文字层提取，不调用模型。按页标注，识别空页避免静默漏页。 */
export async function extractPdf(file,onProgress=()=>{}) {
  if(file.size>10*1024*1024)throw Error('PDF最多10MB');
  const pdfjs=await import('./vendor/pdf.mjs');
  pdfjs.GlobalWorkerOptions.workerSrc=new URL('./vendor/pdf.worker.mjs',import.meta.url).href;
  const task=pdfjs.getDocument({data:new Uint8Array(await file.arrayBuffer()),isEvalSupported:false});
  let doc;
  try {
    doc=await task.promise;
    if(doc.numPages>200)throw Error('PDF最多200页，请拆分后导入');
    const pages=[],empty=[];let chars=0;
    for(let i=1;i<=doc.numPages;i++){
      onProgress(i,doc.numPages);
      const page=await doc.getPage(i),data=await page.getTextContent();
      let text='';
      for(const item of data.items){if('str' in item)text+=item.str+(item.hasEOL?'\n':' ')}
      text=text.replace(/[ \t]+\n/g,'\n').trim();
      if(!text)empty.push(i);
      chars+=text.length;
      if(chars>1000000)throw Error('提取文字超过100万字符，请拆分PDF');
      pages.push(`【第 ${i} 页】\n${text||'【此页未提取到文字，可能是图片或空白页】'}`);
      page.cleanup();
    }
    if(empty.length===doc.numPages)throw Error('这份PDF没有可提取的文字层，需要OCR；当前未提供自动OCR。');
    return {content:pages.join('\n\n'),pageCount:doc.numPages,emptyPages:empty};
  } catch(e) {
    if(e.name==='PasswordException')throw Error('PDF已加密，请先解除密码');
    throw e;
  } finally {await task.destroy()}
}
