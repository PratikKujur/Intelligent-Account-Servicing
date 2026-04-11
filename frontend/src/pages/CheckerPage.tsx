import { useState, useEffect } from 'react'
import type { PendingRequest } from '../types'

export default function CheckerPage() {
  const [requests, setRequests] = useState<PendingRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedRequest, setSelectedRequest] = useState<PendingRequest | null>(null)
  const [checkerId] = useState('CHECKER-001')
  const [rejectionReason, setRejectionReason] = useState('')
  const [processing, setProcessing] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    loadRequests()
  }, [])

  const loadRequests = async () => {
    try {
      const res = await fetch('/api/v1/requests/pending/review')
      const data = await res.json()
      setRequests(data.requests || [])
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

  const handleDecision = async (decision: 'APPROVE' | 'REJECT') => {
    if (!selectedRequest) {
      return
    }

    if (decision === 'REJECT' && !rejectionReason) {
      setMessage({ type: 'error', text: 'Rejection reason required' })
      return
    }

    setProcessing(true)
    setMessage(null)

    try {
      const res = await fetch('/api/v1/checker/decide', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          request_id: selectedRequest.request_id,
          decision,
          checker_id: checkerId,
          rejection_reason: rejectionReason || undefined
        })
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Decision failed')
      }

      const result = await res.json()
      setMessage({ 
        type: 'success', 
        text: decision === 'APPROVE' 
          ? `Approved! RPS: ${result.rps_reference}`
          : 'Request rejected'
      })
      setSelectedRequest(null)
      setRejectionReason('')
      loadRequests()
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed' })
    } finally {
      setProcessing(false)
    }
  }

  if (loading) {
    return <div className="loading"><div className="spinner"></div></div>
  }

  return (
    <div>
      <div className="page-header">
        <h1>Checker Review</h1>
        <p>Review AI-verified name change requests</p>
      </div>

      {message && (
        <div className={`alert alert-${message.type}`}>{message.text}</div>
      )}

      {selectedRequest ? (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Request - {selectedRequest.request_id.slice(0, 8)}</h2>
            <button className="btn btn-outline" onClick={() => setSelectedRequest(null)}>
              Back
            </button>
          </div>

          <div className="review-detail">
            <div>
              <div className="detail-section">
                <h4>Name Change Request</h4>
                <div className="detail-row">
                  <span className="detail-label">Current/Old Name</span>
                  <span className="detail-value">{selectedRequest.name}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">New Name</span>
                  <span className="detail-value">{selectedRequest.extracted_data?.name ? '(See document)' : 'Not provided'}</span>
                </div>
              </div>

              <div className="detail-section">
                <h4>Document Verification</h4>
                {selectedRequest.extracted_data && (
                  <>
                    <div className="detail-row">
                      <span className="detail-label">Name (from Aadhaar)</span>
                      <span className="detail-value">{selectedRequest.extracted_data.name || 'Not found'}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Date of Birth</span>
                      <span className="detail-value">{selectedRequest.extracted_data.date_of_birth || 'Not found'}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Aadhaar Number</span>
                      <span className="detail-value">{selectedRequest.extracted_data.aadhar_number || 'Not found'}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Forgery Flag</span>
                      <span className="detail-value" style={{ color: selectedRequest.extracted_data.forgery_flag ? 'red' : 'green' }}>
                        {selectedRequest.extracted_data.forgery_flag ? 'DETECTED' : 'Not detected'}
                      </span>
                    </div>
                  </>
                )}
              </div>
            </div>

            <div>
              <div className="detail-section">
                <h4>Name Change Verification Scores</h4>
                {selectedRequest.confidence_score ? (
                  <>
                    <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                      <div className="confidence-score">
                        <div className={`score-circle ${getScoreClass(selectedRequest.confidence_score?.name_change_request_score ?? 0)}`}>
                          {selectedRequest.confidence_score?.name_change_request_score ?? 0}%
                        </div>
                        <span className="score-label">Name Change Valid</span>
                      </div>
                      <div className="confidence-score">
                        <div className={`score-circle ${getScoreClass(selectedRequest.confidence_score?.document_to_old_match ?? 0)}`}>
                          {selectedRequest.confidence_score?.document_to_old_match ?? 0}%
                        </div>
                        <span className="score-label">Doc to Old</span>
                      </div>
                      <div className="confidence-score">
                        <div className={`score-circle ${getScoreClass(selectedRequest.confidence_score?.document_to_new_match ?? 0)}`}>
                          {selectedRequest.confidence_score?.document_to_new_match ?? 0}%
                        </div>
                        <span className="score-label">Doc to New</span>
                      </div>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                      Doc to Old: Mid-High = document name similar old name (good). Doc to New: Higher = document name same as new name (good).
                    </div>
                  </>
                ) : (
                  <div style={{ color: 'var(--text-muted)' }}>No scores available</div>
                )}
              </div>

              <div className="detail-section">
                <h4>Other Scores</h4>
                {selectedRequest.confidence_score ? (
                  <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                    <div className="confidence-score">
                      <div className={`score-circle ${getScoreClass(selectedRequest.confidence_score?.dob_match ?? 0)}`}>
                        {selectedRequest.confidence_score?.dob_match ?? 0}%
                      </div>
                      <span className="score-label">DOB Match</span>
                    </div>
                    <div className="confidence-score">
                      <div className={`score-circle ${getScoreClass(selectedRequest.confidence_score?.adhar_match ?? 0)}`}>
                        {selectedRequest.confidence_score?.adhar_match ?? 0}%
                      </div>
                      <span className="score-label">Aadhaar</span>
                    </div>
                    <div className="confidence-score">
                      <div className={`score-circle ${getScoreClass(selectedRequest.confidence_score?.doc_auth ?? 0)}`}>
                        {selectedRequest.confidence_score?.doc_auth ?? 0}%
                      </div>
                      <span className="score-label">Doc Auth</span>
                    </div>
                    <div className="confidence-score">
                      <div className={`score-circle ${getScoreClass(selectedRequest.confidence_score?.overall ?? 0)}`}>
                        {selectedRequest.confidence_score?.overall ?? 0}%
                      </div>
                      <span className="score-label">Overall</span>
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="detail-section">
                <h4>AI Summary</h4>
                <div className="ai-summary">
                  {selectedRequest.ai_summary || 'No summary'}
                </div>
              </div>
            </div>
          </div>

          <div className="decision-form">
            <div className="form-group">
              <label className="form-label">Rejection Reason (required for rejection)</label>
              <textarea
                className="form-input"
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder="Enter reason for rejection..."
                rows={3}
                style={{ resize: 'vertical' }}
              />
            </div>

            <div className="decision-buttons">
              <button 
                className="btn btn-success" 
                onClick={() => handleDecision('APPROVE')}
                disabled={processing}
              >
                Approve
              </button>
              <button 
                className="btn btn-danger" 
                onClick={() => handleDecision('REJECT')}
                disabled={processing || !rejectionReason}
              >
                Reject
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Pending Reviews ({requests.length})</h2>
          </div>

          {requests.length === 0 ? (
            <div className="empty-state">
              <p>No pending requests</p>
            </div>
          ) : (
            <div className="request-list">
              {requests.map((req) => (
                <div key={req.request_id} className="request-item">
                  <div className="request-info">
                    <h3>{req.name}</h3>
                    <p>Customer: {req.customer_id} | ID: {req.request_id.slice(0, 8)}</p>
                  </div>
                  <div className="request-meta">
                    {req.confidence_score && (
                      <div className="confidence-score">
                        <div className={`score-circle ${getScoreClass(req.confidence_score.overall ?? 0)}`}>
                          {req.confidence_score.overall ?? 0}%
                        </div>
                        <span className="score-label">Score</span>
                      </div>
                    )}
                    <span className={`status-badge ${req.ai_recommendation?.includes('APPROVE') ? 'status-approved' : 'status-rejected'}`}>
                      {req.ai_recommendation || 'PENDING'}
                    </span>
                    <button className="btn btn-primary" onClick={() => setSelectedRequest(req)}>
                      Review
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
