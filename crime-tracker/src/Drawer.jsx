import { CloseIcon } from './Icons.jsx'

/**
 * Right-hand drawer on desktop, bottom sheet on small screens. Hidden from focus and AT while closed.
 * The head (drag handle and Close) sits outside the scrolling body, so on the sheet it stays put and the
 * text never scrolls under the button.
 */
export default function Drawer({ open, label, onClose, children }) {
  return (
    <aside className={open ? 'drawer is-open' : 'drawer'} aria-label={label} inert={!open}>
      <div className="drawer__head">
        <div className="drawer__handle" aria-hidden="true" />
        <button type="button" className="btn btn--icon drawer__close" onClick={onClose} aria-label="Close">
          <CloseIcon />
        </button>
      </div>
      <div className="drawer__body">{children}</div>
    </aside>
  )
}
