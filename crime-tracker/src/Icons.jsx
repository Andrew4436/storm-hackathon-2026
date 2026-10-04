// Inline icons, stroke 1.75. Decorative: the button around each one carries the label.
const Icon = ({ children }) => (
  <svg className="icon" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
    {children}
  </svg>
)

export const PlayIcon = () => (
  <Icon>
    <path d="M6.5 4.5v11l9-5.5z" />
  </Icon>
)
export const PauseIcon = () => (
  <Icon>
    <path d="M7 4.5v11M13 4.5v11" />
  </Icon>
)
export const PrevIcon = () => (
  <Icon>
    <path d="M12.5 4.5 7 10l5.5 5.5" />
  </Icon>
)
export const NextIcon = () => (
  <Icon>
    <path d="M7.5 4.5 13 10l-5.5 5.5" />
  </Icon>
)
export const ChevronDownIcon = () => (
  <Icon>
    <path d="m5.5 7.75 4.5 4.5 4.5-4.5" />
  </Icon>
)
export const CloseIcon = () => (
  <Icon>
    <path d="m5 5 10 10M15 5 5 15" />
  </Icon>
)
