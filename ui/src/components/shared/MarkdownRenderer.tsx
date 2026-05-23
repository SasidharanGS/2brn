import ReactMarkdown from 'react-markdown'

export default function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="leading-relaxed whitespace-pre-wrap text-sm" style={{ color: 'var(--text)' }}>
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  )
}
