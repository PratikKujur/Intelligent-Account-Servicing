import { useState, useEffect } from 'react'
import type { PendingRequest } from '../types'

export default function DashboardPage() {
  const [requests, setRequests] = useState<PendingRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({ total: 0, pending: 0, approved: 0, rejected: 0 })

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const res = await fetch('/api/v1/requests')
      const data = await res.json()
      const all = data.requests || []
      setRequests(all)
      setStats({
        total: all.length,
        pending: all.filter((r: PendingRequest) => r.status === 'AI_VERIFIED_PENDING_HUMAN').length,
        approved: all.filter((r: PendingRequest) => r.status === 'RPS_UPDATED').length,
        rejected: all.filter((r: PendingRequest) => r.status === 'REJECTED').length
      })
    } catch (err) {
      console.error('Failed to load:', err)
    } finally {
      setLoading(false)
    }
  }

  const getScoreClass = (score: number) => {
    if (score >= 75) return 'score-high'
    if (score >= 50) return 'score-medium'
    return 'score-low'
  }

  if (loading) {
    return <div className="loading"><div className="spinner"></div></div>
  }

  return (
    <div>
      <div className="page-header">
        <h1>IASW Dashboard</h1>
        <p>Identity Verification Workflow - Human-in-the-Loop System</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
        {[
          { label: 'Total', value: stats.total, color: 'var(--primary)' },
          { label: 'Pending', value: stats.pending, color: 'var(--warning)' },
          { label: 'Approved', value: stats.approved, color: 'var(--success)' },
          { label: 'Rejected', value: stats.rejected, color: 'var(--danger)' }
        ].map((stat) => (
          <div key={stat.label} className="card" style={{ textAlign: 'center' }}>
            <h3 style={{ fontSize: '2rem', fontWeight: 700, color: stat.color }}>{stat.value}</h3>
            <p style={{ color: 'var(--text-muted)' }}>{stat.label}</p>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Recent Requests</h2>
        </div>

        {requests.length === 0 ? (
          <div className="empty-state">
            <p>No requests yet</p>
          </div>
        ) : (
          <div className="request-list">
            {requests.slice(0, 10).map((req) => (
              <div key={req.request_id} className="request-item">
                <div className="request-info">
                  <h3>{req.name}</h3>
                  <p>Customer: {req.customer_id} | {new Date(req.created_at).toLocaleDateString()}</p>
                </div>
                <div className="request-meta">
                  {req.confidence_score && (
                    <div className="confidence-score">
                      <div className={`score-circle ${getScoreClass(req.confidence_score.overall)}`}>
                        {req.confidence_score.overall}%
                      </div>
                    </div>
                  )}
                  <span className={`status-badge status-${req.status === 'RPS_UPDATED' ? 'approved' : req.status === 'REJECTED' ? 'rejected' : 'pending'}`}>
                    {req.status.replace(/_/g, ' ')}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
