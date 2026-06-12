import ReactMarkdown from 'react-markdown'

const SAFE_URL_RE = /^(https?:|mailto:|\/|#)/i

/** Markdown rendered in the minimal reading style (see .m-prose in minimal.css). */
export default function Prose({ content, variant }: { content: string; variant: 'journal' | 'blog' | 'chat' }) {
  return (
    <div className={`m-prose m-prose--${variant}`}>
      <ReactMarkdown urlTransform={(url) => (SAFE_URL_RE.test(url) ? url : '')}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
