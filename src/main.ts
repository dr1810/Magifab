import './style.css'

type Bubble = {
  label: string
  title: string
  text: string
  icon: string
}

const bubbles: Bubble[] = [
  {
    label: 'Who is that?',
    title: 'Meet Elara',
    text: 'Elara is the young inventor at the heart of this story. Right now, she is trying to protect her family’s floating garden.',
    icon: '✦',
  },
  {
    label: 'What’s happening?',
    title: 'A turning point',
    text: 'The wind has changed direction. Elara realizes the garden is drifting toward the storm — and she has a brave choice to make.',
    icon: '◌',
  },
  {
    label: 'Why does it matter?',
    title: 'The hidden meaning',
    text: 'This scene shows that asking for help can be its own kind of courage. It sets up the promise between Elara and her grandfather.',
    icon: '♡',
  },
]

const app = document.querySelector<HTMLDivElement>('#app')

if (!app) throw new Error('Unable to find app root')

app.innerHTML = `
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
              ${bubbles.map((bubble, index) => `<button class="prompt-bubble ${index === 1 ? 'active' : ''}" data-bubble="${index}"><i>${bubble.icon}</i>${bubble.label}<span>+</span></button>`).join('')}
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
`

const answer = document.querySelector<HTMLDivElement>('#answer')
const answerTitle = answer?.querySelector('strong')
const answerText = answer?.querySelector('p')

document.querySelectorAll<HTMLButtonElement>('[data-bubble]').forEach((button) => {
  button.addEventListener('click', () => {
    const bubble = bubbles[Number(button.dataset.bubble)]
    document.querySelectorAll('.prompt-bubble').forEach((item) => item.classList.remove('active'))
    button.classList.add('active')
    if (answer && answerTitle && answerText) {
      answerTitle.textContent = bubble.title
      answerText.textContent = bubble.text
      answer.hidden = false
      answer.classList.remove('reveal')
      void answer.offsetWidth
      answer.classList.add('reveal')
    }
  })
})

document.querySelectorAll<HTMLButtonElement>('[data-scroll]').forEach((button) => {
  button.addEventListener('click', () => document.querySelector(button.dataset.scroll ?? '')?.scrollIntoView({ behavior: 'smooth' }))
})

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

if (!reducedMotion) {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible')
        observer.unobserve(entry.target)
      }
    })
  }, { threshold: 0.16 })

  document.querySelectorAll<HTMLElement>('.section-heading, .scene-card, .companion-card, .feature-grid article').forEach((element) => {
    element.classList.add('reveal-on-scroll')
    observer.observe(element)
  })
}
