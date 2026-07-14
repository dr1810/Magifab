import './style.css'

type Bubble = {
  label: string
  title: string
  text: string
  icon: string
}

type DifficultyCategory = {
  id: string
  label: string
  question: string
  options: string[]
  profileTags: { methods?: string[]; visuals?: string[]; prompts?: string[] }
}

type CompanionProfile = {
  difficultyAreas: string[]
  preferredExplanationMethods: string[]
  preferredVisualAssistance: string[]
  promptFrequency: string
  detailLevel: string
  interactionStyle: string
  explanationTone: string
  preferredPromptTypes: string[]
}

// This registry is the single extension point for new difficulty categories and their follow-up questions.
const difficultyCategories: DifficultyCategory[] = [
  { id: 'emotions', label: 'Understanding emotions', question: 'How would you like your AI companion to help with emotions?', options: ['Explain facial expressions', 'Explain tone of voice', 'Explain body language', 'Explain why the character feels this way', 'Explain hidden emotions', 'Explain emotional changes throughout the scene'], profileTags: { methods: ['emotional context'], visuals: ['facial-expression cues'], prompts: ['emotion insight'] } },
  { id: 'characters', label: 'Remembering characters', question: 'How should I help you remember characters?', options: ['Introduce every new character', "Remind me where I've seen this character before", 'Explain relationships between characters', 'Show a small character card', 'Highlight the character on screen'], profileTags: { methods: ['character context'], visuals: ['character cards', 'on-screen highlights'], prompts: ['character introduction'] } },
  { id: 'relationships', label: 'Understanding relationships', question: 'What would help you understand relationships?', options: ['Family trees', 'Friendship explanations', 'Relationship summaries', 'Explain conflicts', 'Explain alliances'], profileTags: { methods: ['relationship context'], visuals: ['relationship maps'], prompts: ['relationship update'] } },
  { id: 'plot', label: 'Following the plot', question: 'How should I help you follow the story?', options: ['Scene summaries', 'Explain important events', 'Explain why something happened', 'Explain cause and effect', 'Explain what I should pay attention to'], profileTags: { methods: ['plot clarity'], prompts: ['scene summary', 'important event'] } },
  { id: 'previous-events', label: 'Remembering previous events', question: 'How should I remind you about earlier events?', options: ['Quick recaps', 'Timeline view', 'Explain callbacks', 'Remind me of previous scenes', 'Show important past events'], profileTags: { methods: ['memory recap'], visuals: ['timeline'], prompts: ['callback reminder'] } },
  { id: 'conversations', label: 'Understanding conversations', question: 'What would help you during conversations?', options: ['Explain difficult dialogue', 'Slow down explanations', 'Explain references', 'Explain who is speaking', 'Summarize conversations'], profileTags: { methods: ['dialogue clarity'], prompts: ['conversation summary'] } },
  { id: 'jokes', label: 'Understanding jokes', question: 'How should I explain humor?', options: ['Explain visual jokes', 'Explain wordplay', 'Explain sarcasm', 'Explain cultural references', 'Explain why everyone laughed'], profileTags: { methods: ['humor context'], prompts: ['humor explanation'] } },
  { id: 'sarcasm', label: 'Understanding sarcasm', question: 'How would you like sarcasm explained?', options: ['Tell me when someone is sarcastic', 'Explain what they actually mean', 'Explain tone of voice', 'Explain facial expressions'], profileTags: { methods: ['subtext clarity'], visuals: ['tone and expression cues'], prompts: ['sarcasm cue'] } },
  { id: 'vocabulary', label: 'Understanding difficult words', question: 'How should vocabulary be explained?', options: ['Simple definitions', 'Examples', 'Pictures', 'Similar words', 'Explain in simpler language'], profileTags: { methods: ['plain-language definitions'], visuals: ['word pictures'], prompts: ['word explanation'] } },
  { id: 'objects', label: 'Recognizing important objects', question: 'How should important objects be shown?', options: ['Highlight the object', 'Explain why it matters', 'Remind me later if it becomes important', 'Point to the object', 'Show previous appearances'], profileTags: { methods: ['object significance'], visuals: ['object highlights'], prompts: ['important object'] } },
  { id: 'visual-scenes', label: 'Understanding scenes without dialogue', question: 'How should I explain visual scenes?', options: ['Describe actions', 'Explain facial expressions', 'Explain body language', 'Explain visual symbolism', 'Explain environmental clues'], profileTags: { methods: ['visual description'], visuals: ['scene cues'], prompts: ['visual scene explanation'] } },
]

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

const onboarding = document.querySelector<HTMLDivElement>('#onboarding')
const onboardingContent = document.querySelector<HTMLDivElement>('#onboarding-content')
let onboardingStep = 1
const selectedDifficulties = new Set<string>()
const selectedFollowUps = new Map<string, Set<string>>()
const preferences = { promptFrequency: 'Only when I ask', detailLevel: 'Just the essentials', interactionStyle: 'Gentle bubbles', explanationTone: 'Warm and encouraging' }

const optionButton = (label: string, selected: boolean, attributes: string) =>
  `<button type="button" class="choice-chip ${selected ? 'selected' : ''}" ${attributes}><span class="choice-check">✓</span>${label}</button>`

function renderOnboarding() {
  if (!onboardingContent) return
  const stepContent = {
    1: `
      <p class="onboarding-kicker">STEP 1 OF 4 · A LITTLE HELLO</p>
      <h2 id="onboarding-title">Your stories should feel <em>like yours.</em></h2>
      <p class="onboarding-copy">We’ll ask just a few questions to shape a movie companion around the way you like to watch. You can change this any time.</p>
      <div class="onboarding-actions"><button class="primary-button" data-onboarding-next>Let’s begin <span>→</span></button></div>`,
    2: `
      <p class="onboarding-kicker">STEP 2 OF 4 · YOUR VIEWING EXPERIENCE</p>
      <h2 id="onboarding-title">What can feel tricky<br/>while watching?</h2>
      <p class="onboarding-copy">Choose any that apply. We’ll only ask about the areas you select.</p>
      <div class="choice-grid difficulty-grid">${difficultyCategories.map((category) => optionButton(category.label, selectedDifficulties.has(category.id), `data-difficulty="${category.id}" aria-pressed="${selectedDifficulties.has(category.id)}"`)).join('')}</div>
      <div class="onboarding-actions"><button class="secondary-button" data-onboarding-back>Back</button><button class="primary-button" data-onboarding-next ${selectedDifficulties.size ? '' : 'disabled'}>Continue <span>→</span></button></div>`,
    3: `
      <p class="onboarding-kicker">STEP 3 OF 4 · YOUR PERSONAL TOUCHES</p>
      <h2 id="onboarding-title">Tell us what would <em>help most.</em></h2>
      <p class="onboarding-copy">These questions are tailored to the areas you chose. Pick as many helpful ideas as you like.</p>
      <div class="follow-up-list">${difficultyCategories.filter((category) => selectedDifficulties.has(category.id)).map((category) => `
        <fieldset class="follow-up-group"><legend>${category.question}</legend><div class="choice-grid compact">${category.options.map((option) => optionButton(option, selectedFollowUps.get(category.id)?.has(option) ?? false, `data-followup-category="${category.id}" data-followup-option="${option}" aria-pressed="${selectedFollowUps.get(category.id)?.has(option) ?? false}"`)).join('')}</div></fieldset>`).join('')}
      </div>
      <div class="onboarding-actions"><button class="secondary-button" data-onboarding-back>Back</button><button class="primary-button" data-onboarding-next>Continue <span>→</span></button></div>`,
    4: `
      <p class="onboarding-kicker">STEP 4 OF 4 · YOUR COMPANION’S STYLE</p>
      <h2 id="onboarding-title">One last little <em>bit of magic.</em></h2>
      <p class="onboarding-copy">Set the overall feel of your companion. This helps Magifab know when and how to be there.</p>
      <div class="preference-grid">
        ${renderPreference('Prompt frequency', 'promptFrequency', ['Only when I ask', 'At important moments', 'Often, with gentle nudges'])}
        ${renderPreference('Detail level', 'detailLevel', ['Just the essentials', 'A little more context', 'Give me the full picture'])}
        ${renderPreference('Interaction style', 'interactionStyle', ['Gentle bubbles', 'Clear on-screen cues', 'A mix of both'])}
        ${renderPreference('Explanation tone', 'explanationTone', ['Warm and encouraging', 'Simple and direct', 'Playful and curious'])}
      </div>
      <div class="onboarding-actions"><button class="secondary-button" data-onboarding-back>Back</button><button class="primary-button" data-create-profile>Create my companion <span>✦</span></button></div>`,
  }[onboardingStep]

  onboardingContent.innerHTML = stepContent ?? ''
  document.querySelectorAll('.onboarding-progress i').forEach((item, index) => item.classList.toggle('active', index < onboardingStep))
  bindOnboardingEvents()
}

function renderPreference(title: string, key: keyof typeof preferences, options: string[]) {
  return `<fieldset class="preference-group"><legend>${title}</legend>${options.map((option) => `<button type="button" class="preference-option ${preferences[key] === option ? 'selected' : ''}" data-preference="${key}" data-value="${option}" aria-pressed="${preferences[key] === option}">${option}</button>`).join('')}</fieldset>`
}

function bindOnboardingEvents() {
  document.querySelector<HTMLButtonElement>('[data-onboarding-next]')?.addEventListener('click', () => { onboardingStep += 1; renderOnboarding() })
  document.querySelector<HTMLButtonElement>('[data-onboarding-back]')?.addEventListener('click', () => { onboardingStep -= 1; renderOnboarding() })
  document.querySelectorAll<HTMLButtonElement>('[data-difficulty]').forEach((button) => button.addEventListener('click', () => {
    const id = button.dataset.difficulty ?? ''
    selectedDifficulties.has(id) ? selectedDifficulties.delete(id) : selectedDifficulties.add(id)
    renderOnboarding()
  }))
  document.querySelectorAll<HTMLButtonElement>('[data-followup-category]').forEach((button) => button.addEventListener('click', () => {
    const category = button.dataset.followupCategory ?? ''
    const option = button.dataset.followupOption ?? ''
    const selections = selectedFollowUps.get(category) ?? new Set<string>()
    selections.has(option) ? selections.delete(option) : selections.add(option)
    selectedFollowUps.set(category, selections)
    renderOnboarding()
  }))
  document.querySelectorAll<HTMLButtonElement>('[data-preference]').forEach((button) => button.addEventListener('click', () => {
    const key = button.dataset.preference as keyof typeof preferences
    preferences[key] = button.dataset.value ?? preferences[key]
    renderOnboarding()
  }))
  document.querySelector<HTMLButtonElement>('[data-create-profile]')?.addEventListener('click', showProfile)
}

function showProfile() {
  const categories = difficultyCategories.filter((category) => selectedDifficulties.has(category.id))
  const selectedOptions = [...selectedFollowUps.values()].flatMap((options) => [...options])
  const hasVisualPreference = (option: string) => /picture|highlight|point|card|timeline|tree|facial|body|visual|environment|appearance/i.test(option)
  const profile: CompanionProfile = {
    difficultyAreas: categories.map((category) => category.label),
    preferredExplanationMethods: [...new Set([...categories.flatMap((category) => category.profileTags.methods ?? []), ...selectedOptions.filter((option) => !hasVisualPreference(option))])],
    preferredVisualAssistance: [...new Set([...categories.flatMap((category) => category.profileTags.visuals ?? []), ...selectedOptions.filter(hasVisualPreference)])],
    promptFrequency: preferences.promptFrequency,
    detailLevel: preferences.detailLevel,
    interactionStyle: preferences.interactionStyle,
    explanationTone: preferences.explanationTone,
    preferredPromptTypes: [...new Set(categories.flatMap((category) => category.profileTags.prompts ?? []))],
  }
  onboardingContent!.innerHTML = `
    <p class="onboarding-kicker">YOUR MAGIFAB PROFILE</p>
    <h2 id="onboarding-title">Your companion is <em>ready.</em></h2>
    <p class="onboarding-copy">This is the AI profile Magifab will use to shape its prompts and explanations during movie playback.</p>
    <div class="profile-summary">
      <div><span>HELP WITH</span><strong>${profile.difficultyAreas.join(' · ')}</strong></div>
      <div><span>STYLE</span><strong>${profile.explanationTone} · ${profile.detailLevel}</strong></div>
      <div><span>PROMPTS</span><strong>${profile.promptFrequency} · ${profile.interactionStyle}</strong></div>
    </div>
    <div class="onboarding-actions"><button class="primary-button" data-close-onboarding>Start watching <span>→</span></button></div>`
  document.querySelectorAll('.onboarding-progress i').forEach((item) => item.classList.add('active'))
  bindCloseEvents()
}

function openOnboarding() {
  onboardingStep = 1
  onboarding?.classList.add('open')
  onboarding?.setAttribute('aria-hidden', 'false')
  document.body.classList.add('dialog-open')
  renderOnboarding()
}

function closeOnboarding() {
  onboarding?.classList.remove('open')
  onboarding?.setAttribute('aria-hidden', 'true')
  document.body.classList.remove('dialog-open')
}

function bindCloseEvents() {
  document.querySelectorAll<HTMLElement>('[data-close-onboarding]').forEach((element) => element.addEventListener('click', closeOnboarding))
}

document.querySelectorAll<HTMLButtonElement>('[data-onboarding]').forEach((button) => button.addEventListener('click', openOnboarding))
bindCloseEvents()
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeOnboarding() })

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
