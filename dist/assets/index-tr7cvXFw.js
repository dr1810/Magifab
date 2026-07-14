(function(){const a=document.createElement("link").relList;if(a&&a.supports&&a.supports("modulepreload"))return;for(const e of document.querySelectorAll('link[rel="modulepreload"]'))i(e);new MutationObserver(e=>{for(const s of e)if(s.type==="childList")for(const l of s.addedNodes)l.tagName==="LINK"&&l.rel==="modulepreload"&&i(l)}).observe(document,{childList:!0,subtree:!0});function n(e){const s={};return e.integrity&&(s.integrity=e.integrity),e.referrerPolicy&&(s.referrerPolicy=e.referrerPolicy),e.crossOrigin==="use-credentials"?s.credentials="include":e.crossOrigin==="anonymous"?s.credentials="omit":s.credentials="same-origin",s}function i(e){if(e.ep)return;e.ep=!0;const s=n(e);fetch(e.href,s)}})();const b=[{id:"emotions",label:"Understanding emotions",question:"How would you like your AI companion to help with emotions?",options:["Explain facial expressions","Explain tone of voice","Explain body language","Explain why the character feels this way","Explain hidden emotions","Explain emotional changes throughout the scene"],profileTags:{methods:["emotional context"],visuals:["facial-expression cues"],prompts:["emotion insight"]}},{id:"characters",label:"Remembering characters",question:"How should I help you remember characters?",options:["Introduce every new character","Remind me where I've seen this character before","Explain relationships between characters","Show a small character card","Highlight the character on screen"],profileTags:{methods:["character context"],visuals:["character cards","on-screen highlights"],prompts:["character introduction"]}},{id:"relationships",label:"Understanding relationships",question:"What would help you understand relationships?",options:["Family trees","Friendship explanations","Relationship summaries","Explain conflicts","Explain alliances"],profileTags:{methods:["relationship context"],visuals:["relationship maps"],prompts:["relationship update"]}},{id:"plot",label:"Following the plot",question:"How should I help you follow the story?",options:["Scene summaries","Explain important events","Explain why something happened","Explain cause and effect","Explain what I should pay attention to"],profileTags:{methods:["plot clarity"],prompts:["scene summary","important event"]}},{id:"previous-events",label:"Remembering previous events",question:"How should I remind you about earlier events?",options:["Quick recaps","Timeline view","Explain callbacks","Remind me of previous scenes","Show important past events"],profileTags:{methods:["memory recap"],visuals:["timeline"],prompts:["callback reminder"]}},{id:"conversations",label:"Understanding conversations",question:"What would help you during conversations?",options:["Explain difficult dialogue","Slow down explanations","Explain references","Explain who is speaking","Summarize conversations"],profileTags:{methods:["dialogue clarity"],prompts:["conversation summary"]}},{id:"jokes",label:"Understanding jokes",question:"How should I explain humor?",options:["Explain visual jokes","Explain wordplay","Explain sarcasm","Explain cultural references","Explain why everyone laughed"],profileTags:{methods:["humor context"],prompts:["humor explanation"]}},{id:"sarcasm",label:"Understanding sarcasm",question:"How would you like sarcasm explained?",options:["Tell me when someone is sarcastic","Explain what they actually mean","Explain tone of voice","Explain facial expressions"],profileTags:{methods:["subtext clarity"],visuals:["tone and expression cues"],prompts:["sarcasm cue"]}},{id:"vocabulary",label:"Understanding difficult words",question:"How should vocabulary be explained?",options:["Simple definitions","Examples","Pictures","Similar words","Explain in simpler language"],profileTags:{methods:["plain-language definitions"],visuals:["word pictures"],prompts:["word explanation"]}},{id:"objects",label:"Recognizing important objects",question:"How should important objects be shown?",options:["Highlight the object","Explain why it matters","Remind me later if it becomes important","Point to the object","Show previous appearances"],profileTags:{methods:["object significance"],visuals:["object highlights"],prompts:["important object"]}},{id:"visual-scenes",label:"Understanding scenes without dialogue",question:"How should I explain visual scenes?",options:["Describe actions","Explain facial expressions","Explain body language","Explain visual symbolism","Explain environmental clues"],profileTags:{methods:["visual description"],visuals:["scene cues"],prompts:["visual scene explanation"]}}],w=[{label:"Who is that?",title:"Meet Elara",text:"Elara is the young inventor at the heart of this story. Right now, she is trying to protect her family’s floating garden.",icon:"✦"},{label:"What’s happening?",title:"A turning point",text:"The wind has changed direction. Elara realizes the garden is drifting toward the storm — and she has a brave choice to make.",icon:"◌"},{label:"Why does it matter?",title:"The hidden meaning",text:"This scene shows that asking for help can be its own kind of courage. It sets up the promise between Elara and her grandfather.",icon:"♡"}],E=document.querySelector("#app");if(!E)throw new Error("Unable to find app root");E.innerHTML=`
  <main>
    <nav class="nav container" aria-label="Main navigation">
      <a class="brand" href="#top" aria-label="Magifab home"><span class="brand-star">✦</span> magifab</a>
      <div class="nav-links">
        <a href="#how-it-works">How it works</a>
        <a href="#stories">Stories</a>
        <a href="#about">About us</a>
      </div>
      <button class="nav-cta" data-onboarding>Try Magifab <span>→</span></button>
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
          <button class="primary-button" data-onboarding>Begin your journey <span>→</span></button>
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
              ${w.map((t,a)=>`<button class="prompt-bubble ${a===1?"active":""}" data-bubble="${a}"><i>${t.icon}</i>${t.label}<span>+</span></button>`).join("")}
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
    <div class="onboarding" id="onboarding" aria-hidden="true">
      <div class="onboarding-backdrop" data-close-onboarding></div>
      <section class="onboarding-panel" role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
        <button class="close-onboarding" type="button" aria-label="Close onboarding" data-close-onboarding>×</button>
        <div class="onboarding-brand"><span>✦</span> magifab</div>
        <div class="onboarding-progress" aria-hidden="true"><i></i><i></i><i></i><i></i></div>
        <div id="onboarding-content"></div>
      </section>
    </div>
  </main>
`;const r=document.querySelector("#answer"),f=r==null?void 0:r.querySelector("strong"),g=r==null?void 0:r.querySelector("p");document.querySelectorAll("[data-bubble]").forEach(t=>{t.addEventListener("click",()=>{const a=w[Number(t.dataset.bubble)];document.querySelectorAll(".prompt-bubble").forEach(n=>n.classList.remove("active")),t.classList.add("active"),r&&f&&g&&(f.textContent=a.title,g.textContent=a.text,r.hidden=!1,r.classList.remove("reveal"),r.offsetWidth,r.classList.add("reveal"))})});document.querySelectorAll("[data-scroll]").forEach(t=>{t.addEventListener("click",()=>{var a;return(a=document.querySelector(t.dataset.scroll??""))==null?void 0:a.scrollIntoView({behavior:"smooth"})})});const o=document.querySelector("#onboarding"),v=document.querySelector("#onboarding-content");let u=1;const c=new Set,h=new Map,d={promptFrequency:"Only when I ask",detailLevel:"Just the essentials",interactionStyle:"Gentle bubbles",explanationTone:"Warm and encouraging"},y=(t,a,n)=>`<button type="button" class="choice-chip ${a?"selected":""}" ${n}><span class="choice-check">✓</span>${t}</button>`;function p(){if(!v)return;const t={1:`
      <p class="onboarding-kicker">STEP 1 OF 4 · A LITTLE HELLO</p>
      <h2 id="onboarding-title">Your stories should feel <em>like yours.</em></h2>
      <p class="onboarding-copy">We’ll ask just a few questions to shape a movie companion around the way you like to watch. You can change this any time.</p>
      <div class="onboarding-actions"><button class="primary-button" data-onboarding-next>Let’s begin <span>→</span></button></div>`,2:`
      <p class="onboarding-kicker">STEP 2 OF 4 · YOUR VIEWING EXPERIENCE</p>
      <h2 id="onboarding-title">What can feel tricky<br/>while watching?</h2>
      <p class="onboarding-copy">Choose any that apply. We’ll only ask about the areas you select.</p>
      <div class="choice-grid difficulty-grid">${b.map(a=>y(a.label,c.has(a.id),`data-difficulty="${a.id}" aria-pressed="${c.has(a.id)}"`)).join("")}</div>
      <div class="onboarding-actions"><button class="secondary-button" data-onboarding-back>Back</button><button class="primary-button" data-onboarding-next ${c.size?"":"disabled"}>Continue <span>→</span></button></div>`,3:`
      <p class="onboarding-kicker">STEP 3 OF 4 · YOUR PERSONAL TOUCHES</p>
      <h2 id="onboarding-title">Tell us what would <em>help most.</em></h2>
      <p class="onboarding-copy">These questions are tailored to the areas you chose. Pick as many helpful ideas as you like.</p>
      <div class="follow-up-list">${b.filter(a=>c.has(a.id)).map(a=>`
        <fieldset class="follow-up-group"><legend>${a.question}</legend><div class="choice-grid compact">${a.options.map(n=>{var i,e;return y(n,((i=h.get(a.id))==null?void 0:i.has(n))??!1,`data-followup-category="${a.id}" data-followup-option="${n}" aria-pressed="${((e=h.get(a.id))==null?void 0:e.has(n))??!1}"`)}).join("")}</div></fieldset>`).join("")}
      </div>
      <div class="onboarding-actions"><button class="secondary-button" data-onboarding-back>Back</button><button class="primary-button" data-onboarding-next>Continue <span>→</span></button></div>`,4:`
      <p class="onboarding-kicker">STEP 4 OF 4 · YOUR COMPANION’S STYLE</p>
      <h2 id="onboarding-title">One last little <em>bit of magic.</em></h2>
      <p class="onboarding-copy">Set the overall feel of your companion. This helps Magifab know when and how to be there.</p>
      <div class="preference-grid">
        ${m("Prompt frequency","promptFrequency",["Only when I ask","At important moments","Often, with gentle nudges"])}
        ${m("Detail level","detailLevel",["Just the essentials","A little more context","Give me the full picture"])}
        ${m("Interaction style","interactionStyle",["Gentle bubbles","Clear on-screen cues","A mix of both"])}
        ${m("Explanation tone","explanationTone",["Warm and encouraging","Simple and direct","Playful and curious"])}
      </div>
      <div class="onboarding-actions"><button class="secondary-button" data-onboarding-back>Back</button><button class="primary-button" data-create-profile>Create my companion <span>✦</span></button></div>`}[u];v.innerHTML=t??"",document.querySelectorAll(".onboarding-progress i").forEach((a,n)=>a.classList.toggle("active",n<u)),S()}function m(t,a,n){return`<fieldset class="preference-group"><legend>${t}</legend>${n.map(i=>`<button type="button" class="preference-option ${d[a]===i?"selected":""}" data-preference="${a}" data-value="${i}" aria-pressed="${d[a]===i}">${i}</button>`).join("")}</fieldset>`}function S(){var t,a,n;(t=document.querySelector("[data-onboarding-next]"))==null||t.addEventListener("click",()=>{u+=1,p()}),(a=document.querySelector("[data-onboarding-back]"))==null||a.addEventListener("click",()=>{u-=1,p()}),document.querySelectorAll("[data-difficulty]").forEach(i=>i.addEventListener("click",()=>{const e=i.dataset.difficulty??"";c.has(e)?c.delete(e):c.add(e),p()})),document.querySelectorAll("[data-followup-category]").forEach(i=>i.addEventListener("click",()=>{const e=i.dataset.followupCategory??"",s=i.dataset.followupOption??"",l=h.get(e)??new Set;l.has(s)?l.delete(s):l.add(s),h.set(e,l),p()})),document.querySelectorAll("[data-preference]").forEach(i=>i.addEventListener("click",()=>{const e=i.dataset.preference;d[e]=i.dataset.value??d[e],p()})),(n=document.querySelector("[data-create-profile]"))==null||n.addEventListener("click",L)}function L(){const t=b.filter(e=>c.has(e.id)),a=[...h.values()].flatMap(e=>[...e]),n=e=>/picture|highlight|point|card|timeline|tree|facial|body|visual|environment|appearance/i.test(e),i={difficultyAreas:t.map(e=>e.label),preferredExplanationMethods:[...new Set([...t.flatMap(e=>e.profileTags.methods??[]),...a.filter(e=>!n(e))])],preferredVisualAssistance:[...new Set([...t.flatMap(e=>e.profileTags.visuals??[]),...a.filter(n)])],promptFrequency:d.promptFrequency,detailLevel:d.detailLevel,interactionStyle:d.interactionStyle,explanationTone:d.explanationTone,preferredPromptTypes:[...new Set(t.flatMap(e=>e.profileTags.prompts??[]))]};v.innerHTML=`
    <p class="onboarding-kicker">YOUR MAGIFAB PROFILE</p>
    <h2 id="onboarding-title">Your companion is <em>ready.</em></h2>
    <p class="onboarding-copy">This is the AI profile Magifab will use to shape its prompts and explanations during movie playback.</p>
    <div class="profile-summary">
      <div><span>HELP WITH</span><strong>${i.difficultyAreas.join(" · ")}</strong></div>
      <div><span>STYLE</span><strong>${i.explanationTone} · ${i.detailLevel}</strong></div>
      <div><span>PROMPTS</span><strong>${i.promptFrequency} · ${i.interactionStyle}</strong></div>
    </div>
    <div class="onboarding-actions"><button class="primary-button" data-close-onboarding>Start watching <span>→</span></button></div>`,document.querySelectorAll(".onboarding-progress i").forEach(e=>e.classList.add("active")),k()}function T(){u=1,o==null||o.classList.add("open"),o==null||o.setAttribute("aria-hidden","false"),document.body.classList.add("dialog-open"),p()}function x(){o==null||o.classList.remove("open"),o==null||o.setAttribute("aria-hidden","true"),document.body.classList.remove("dialog-open")}function k(){document.querySelectorAll("[data-close-onboarding]").forEach(t=>t.addEventListener("click",x))}document.querySelectorAll("[data-onboarding]").forEach(t=>t.addEventListener("click",T));k();document.addEventListener("keydown",t=>{t.key==="Escape"&&x()});const q=window.matchMedia("(prefers-reduced-motion: reduce)").matches;if(!q){const t=new IntersectionObserver(a=>{a.forEach(n=>{n.isIntersecting&&(n.target.classList.add("is-visible"),t.unobserve(n.target))})},{threshold:.16});document.querySelectorAll(".section-heading, .scene-card, .companion-card, .feature-grid article").forEach(a=>{a.classList.add("reveal-on-scroll"),t.observe(a)})}
