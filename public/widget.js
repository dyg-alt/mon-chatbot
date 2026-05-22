(function() {
  const btn = document.createElement('button');
  btn.innerHTML = '💬';
  btn.style.cssText = 'position:fixed;bottom:20px;right:20px;width:60px;height:60px;border-radius:50%;background:#007bff;color:white;border:none;cursor:pointer;font-size:24px;z-index:999;box-shadow:0 4px 6px rgba(0,0,0,0.2);';
  
  const modal = document.createElement('div');
  modal.style.cssText = 'display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:1000;';
  
  const container = document.createElement('div');
  container.style.cssText = 'position:relative;width:500px;height:700px;margin:50px auto;background:white;border-radius:10px;overflow:hidden;';
  
  const closeBtn = document.createElement('button');
  closeBtn.innerHTML = '✕';
  closeBtn.style.cssText = 'position:absolute;top:10px;right:10px;background:red;color:white;border:none;width:30px;height:30px;border-radius:50%;cursor:pointer;z-index:1001;';
  
  const iframe = document.createElement('iframe');
  iframe.src = 'https://mon-chatbot-six.vercel.app/';
  iframe.style.cssText = 'width:100%;height:100%;border:none;';
  
  container.appendChild(closeBtn);
  container.appendChild(iframe);
  modal.appendChild(container);
  
  btn.onclick = () => modal.style.display = 'flex';
  closeBtn.onclick = () => modal.style.display = 'none';
  modal.onclick = (e) => e.target === modal && (modal.style.display = 'none');
  
  document.body.appendChild(btn);
  document.body.appendChild(modal);
})();
