import ReactMarkdown from 'react-markdown'

const SAFE_URL_RE = /^(https?:|mailto:|\/|#)/i

export default function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="leading-relaxed whitespace-pre-wrap text-sm" style={{ color: 'var(--text)' }}>
      <ReactMarkdown urlTransform={(url) => (SAFE_URL_RE.test(url) ? url : '')}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
