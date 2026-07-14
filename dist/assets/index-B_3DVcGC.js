(function(){const e=document.createElement("link").relList;if(e&&e.supports&&e.supports("modulepreload"))return;for(const a of document.querySelectorAll('link[rel="modulepreload"]'))n(a);new MutationObserver(a=>{for(const s of a)if(s.type==="childList")for(const o of s.addedNodes)o.tagName==="LINK"&&o.rel==="modulepreload"&&n(o)}).observe(document,{childList:!0,subtree:!0});function r(a){const s={};return a.integrity&&(s.integrity=a.integrity),a.referrerPolicy&&(s.referrerPolicy=a.referrerPolicy),a.crossOrigin==="use-credentials"?s.credentials="include":a.crossOrigin==="anonymous"?s.credentials="omit":s.credentials="same-origin",s}function n(a){if(a.ep)return;a.ep=!0;const s=r(a);fetch(a.href,s)}})();const d=[{label:"Who is that?",title:"Meet Elara",text:"Elara is the young inventor at the heart of this story. Right now, she is trying to protect her family’s floating garden.",icon:"✦"},{label:"What’s happening?",title:"A turning point",text:"The wind has changed direction. Elara realizes the garden is drifting toward the storm — and she has a brave choice to make.",icon:"◌"},{label:"Why does it matter?",title:"The hidden meaning",text:"This scene shows that asking for help can be its own kind of courage. It sets up the promise between Elara and her grandfather.",icon:"♡"}],h=document.querySelector("#app");if(!h)throw new Error("Unable to find app root");h.innerHTML=`
  <main>
    <nav class="nav container" aria-label="Main navigation">
      <a class="brand" href="#top" aria-label="Magifab home"><span class="brand-star">✦</span> magifab</a>
      <div class="nav-links">
        <a href="#how-it-works">How it works</a>
        <a href="#stories">Stories</a>
        <a href="#about">About us</a>
      </div>
      <button class="nav-cta" data-scroll="#watch">Try Magifab <span>→</span></button>
    </nav>

    <section class="hero" id="top">
      <div class="star-field" aria-hidden="true"></div>
      <div class="moon" aria-hidden="true"></div>
      <div class="cloud cloud-one" aria-hidden="true"></div>
      <div class="cloud cloud-two" aria-hidden="true"></div>
      <div class="magic-sparks" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></div>
      <div class="container hero-content">
        <p class="eyebrow">A more magical way to watch</p>
        <h1>Every story deserves<br/><em>to be understood.</em></h1>
        <p class="hero-copy">Magifab is your gentle movie companion — here to explain the moments, characters, and feelings that make every story come alive.</p>
        <div class="hero-actions">
          <button class="primary-button" data-scroll="#watch">Begin your journey <span>→</span></button>
          <button class="text-button" data-scroll="#how-it-works"><span class="play-icon">▶</span> See how it works</button>
        </div>
      </div>
      <div class="hero-horizon" aria-hidden="true">
        <span class="tower tower-left"></span><span class="tower tower-center"></span><span class="tower tower-right"></span>
        <span class="hill hill-left"></span><span class="hill hill-right"></span>
      </div>
      <div class="scroll-hint" aria-hidden="true"><span>SCROLL TO EXPLORE</span><i></i></div>
    </section>

    <section class="watch-section" id="watch">
      <div class="container">
        <div class="section-heading">
          <p class="eyebrow gold">YOUR COMPANION AWAITS</p>
          <h2>Watch at your own<br/><em>wonderful pace.</em></h2>
        </div>
        <div class="watch-layout">
          <div class="scene-card" aria-label="Movie scene preview">
            <div class="scene-sky"><span class="scene-sun"></span><span class="scene-cloud"></span></div>
            <div class="scene-mountain back"></div><div class="scene-mountain front"></div>
            <div class="garden"><span class="tree t1"></span><span class="tree t2"></span><span class="tree t3"></span></div>
            <div class="character character-a"><i></i></div><div class="character character-b"><i></i></div>
            <div class="scene-info"><span>THE LUMINA GARDEN</span><strong>Chapter 04 · A change in the wind</strong></div>
            <button class="scene-play" aria-label="Play scene">▶</button>
            <div class="scene-progress"><span></span></div>
          </div>
          <aside class="companion-card" aria-live="polite">
            <div class="companion-top"><span class="orb">✦</span><span><strong>MAGIFAB IS HERE</strong><small>Your movie friend</small></span></div>
            <p class="companion-question">Need a little help<br/>with this moment?</p>
            <div class="bubble-list" role="group" aria-label="Scene guidance prompts">
              ${d.map((t,e)=>`<button class="prompt-bubble ${e===1?"active":""}" data-bubble="${e}"><i>${t.icon}</i>${t.label}<span>+</span></button>`).join("")}
            </div>
            <div class="answer" id="answer" hidden><strong></strong><p></p></div>
          </aside>
        </div>
      </div>
    </section>

    <section class="features" id="how-it-works">
      <div class="container">
        <p class="eyebrow gold center">MADE FOR EVERY KIND OF VIEWER</p>
        <h2 class="center">A friend in every <em>frame.</em></h2>
        <div class="feature-grid">
          <article><div class="feature-icon">◌</div><h3>Gentle explanations</h3><p>Tap a bubble whenever you want clarity. Magifab explains without taking you out of the moment.</p></article>
          <article><div class="feature-icon">✧</div><h3>Know the characters</h3><p>Keep track of who’s who, what they want, and the connections that make the story matter.</p></article>
          <article><div class="feature-icon">⌁</div><h3>Follow the feeling</h3><p>Discover the small details and emotional threads woven through each beautiful scene.</p></article>
        </div>
      </div>
    </section>

    <footer id="about"><div class="container footer-inner"><a class="brand" href="#top"><span class="brand-star">✦</span> magifab</a><p>Every story, for everyone.</p><span>Made with a little more magic.</span></div></footer>
  </main>
`;const i=document.querySelector("#answer"),c=i==null?void 0:i.querySelector("strong"),l=i==null?void 0:i.querySelector("p");document.querySelectorAll("[data-bubble]").forEach(t=>{t.addEventListener("click",()=>{const e=d[Number(t.dataset.bubble)];document.querySelectorAll(".prompt-bubble").forEach(r=>r.classList.remove("active")),t.classList.add("active"),i&&c&&l&&(c.textContent=e.title,l.textContent=e.text,i.hidden=!1,i.classList.remove("reveal"),i.offsetWidth,i.classList.add("reveal"))})});document.querySelectorAll("[data-scroll]").forEach(t=>{t.addEventListener("click",()=>{var e;return(e=document.querySelector(t.dataset.scroll??""))==null?void 0:e.scrollIntoView({behavior:"smooth"})})});const p=window.matchMedia("(prefers-reduced-motion: reduce)").matches;if(!p){const t=new IntersectionObserver(e=>{e.forEach(r=>{r.isIntersecting&&(r.target.classList.add("is-visible"),t.unobserve(r.target))})},{threshold:.16});document.querySelectorAll(".section-heading, .scene-card, .companion-card, .feature-grid article").forEach(e=>{e.classList.add("reveal-on-scroll"),t.observe(e)})}
