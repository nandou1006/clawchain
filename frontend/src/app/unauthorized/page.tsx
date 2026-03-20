export default function UnauthorizedPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen" style={{ background: "var(--bg)" }}>
      <h1 className="text-2xl font-bold" style={{ color: "var(--text)" }}>无法访问</h1>
      <p className="mt-2" style={{ color: "var(--text-secondary)" }}>请在URL中提供有效的 user_id 参数</p>
      <p className="text-sm mt-4" style={{ color: "var(--text-muted)" }}>示例: localhost:3000/?user_id=ethannan</p>
    </div>
  );
}