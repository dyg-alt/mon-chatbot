(function() {
  const btn = document.createElement('button');
  btn.innerHTML = '💬';
  btn.style.cssText = 'position:fixed;bottom:20px;right:20px;width:60px;height:60px;border-radius:50%;background:#007bff;color:white;border:none;cursor:pointer;font-size:24px;z-index:999;box-shadow:0 4px 6px rgba(0,0,0,0.2);transition:0.3s;';
  
  const panel = document.createElement('div');
  panel.style.cssText = 'position:fixed;right:0;top:0;width:0;height:100%;background:white;box-shadow:-2px 0 10px rgba(0,0,0,0.2);z-index:998;transition:width 0.3s;overflow:hidden;';
  
  const closeBtn = document.createElement('button');
  closeBtn.innerHTML = '✕';
  closeBtn.style.cssText = 'position:absolute;top:10px;right:10px;background:red;color:white;border:none;width:30px;height:30px;border-radius:50%;cursor:pointer;z-index:1001;';
  
  const iframe = document.createElement('iframe');
  iframe.src = 'https://mon-chatbot-six.vercel.app/';
  iframe.style.cssText = 'width:100%;height:100%;border:none;';
  
  panel.appendChild(closeBtn);
  panel.appendChild(iframe);
  
  let isOpen = false;
  
  btn.onclick = () => {
    isOpen = !isOpen;
    panel.style.width = isOpen ? '400px' : '0';
  };
  
  closeBtn.onclick = () => {
    isOpen = false;
    panel.style.width = '0';
  };
  
  document.body.appendChild(btn);
  document.body.appendChild(panel);
})();
