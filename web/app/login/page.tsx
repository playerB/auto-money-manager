export default function LoginPage({
  searchParams,
}: {
  searchParams: { error?: string };
}) {
  return (
    <div className="login-wrap">
      <div className="card login-card">
        <h1 style={{ fontSize: 20, margin: "0 0 4px" }}>💸 Money Manager</h1>
        <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 0 }}>
          Enter your password to continue.
        </p>
        <form method="post" action="/api/login">
          <input
            type="password"
            name="password"
            placeholder="Password"
            autoFocus
            required
          />
          {searchParams?.error ? (
            <div className="error">Incorrect password.</div>
          ) : null}
          <button className="btn" type="submit" style={{ width: "100%", marginTop: 10 }}>
            Sign in
          </button>
        </form>
      </div>
    </div>
  );
}
