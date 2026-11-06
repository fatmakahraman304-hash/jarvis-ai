/* Existing voice/settings preferences; no local design workspace. */
(function () {
  const JV=window.JV;if(!JV)return;
  const $=s=>document.querySelector(s);
  JV.applyPreferences=()=>{
    const pref=JV.settings.theme||'dark';
    document.documentElement.dataset.theme=pref==='system'?(matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'):pref;
    $('#pref-theme').value=pref;$('#pref-length').value=JV.settings.response_length||'normal';
  };
  $('#pref-theme').onchange=e=>JV.saveSettings({theme:e.target.value});
  $('#pref-length').onchange=e=>JV.saveSettings({response_length:e.target.value});
  matchMedia('(prefers-color-scheme: light)').addEventListener('change',()=>JV.applyPreferences());
  $('#offline-save').onclick=async()=>{
    try {await JV.api('/api/keys',{body:{VOSK_MODEL_PATH:$('#offline-path').value}});$('#offline-result').textContent='Model yolu kaydedildi.';}
    catch(e){$('#offline-result').textContent=e.message;}
  };
  JV.applyPreferences();
})();
