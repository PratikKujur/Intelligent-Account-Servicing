import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function IntakePage() {
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    oldName: '',
    newName: '',
    dateOfBirth: '',
    adharNumber: ''
  })
  const [document, setDocument] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setSuccess(null)

    if (formData.oldName.toLowerCase() === formData.newName.toLowerCase()) {
      setError('New name must be different from current name to process a name change request')
      setLoading(false)
      return
    }

    const formDataObj = new FormData()
    formDataObj.append('old_name', formData.oldName)
    formDataObj.append('new_name', formData.newName)
    if (formData.dateOfBirth) formDataObj.append('date_of_birth', formData.dateOfBirth)
    if (formData.adharNumber) formDataObj.append('aadhar_number', formData.adharNumber)
    if (document) formDataObj.append('document', document)

    try {
      const response = await fetch('/api/v1/requests/submit', {
        method: 'POST',
        body: formDataObj,
      })

      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Submission failed')
      }

      const result = await response.json()
      setSuccess(`Request submitted! ID: ${result.request_id}`)
      setFormData({ oldName: '', newName: '', dateOfBirth: '', adharNumber: '' })
      setDocument(null)
      setTimeout(() => navigate('/checker'), 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submission failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Identity Verification Request</h1>
        <p>Submit an Aadhaar verification request for AI processing</p>
      </div>

      <div className="card">
        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Current Legal Name *</label>
            <input
              type="text"
              className="form-input"
              value={formData.oldName}
              onChange={(e) => setFormData({ ...formData, oldName: e.target.value })}
              placeholder="Enter current legal name"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">New Legal Name *</label>
            <input
              type="text"
              className="form-input"
              value={formData.newName}
              onChange={(e) => setFormData({ ...formData, newName: e.target.value })}
              placeholder="Enter new legal name"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Date of Birth</label>
            <input
              type="text"
              className="form-input"
              value={formData.dateOfBirth}
              onChange={(e) => {
                let value = e.target.value.replace(/[^\d-]/g, '');
                if (value.length === 2 && !value.includes('-')) {
                  value = value + '-';
                } else if (value.length === 5 && value.split('-').length === 2) {
                  value = value + '-';
                }
                if (value.length <= 10) {
                  setFormData({ ...formData, dateOfBirth: value });
                }
              }}
              placeholder="DD-MM-YYYY"
              maxLength={10}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Aadhaar Number</label>
            <input
              type="text"
              className="form-input"
              value={formData.adharNumber}
              onChange={(e) => setFormData({ ...formData, adharNumber: e.target.value })}
              placeholder="XXXX XXXX XXXX"
              maxLength={14}
            />
            <p className="form-help">12 digit Aadhaar number (optional)</p>
          </div>

          <div className="form-group">
            <label className="form-label">Aadhaar Document</label>
            <div className={`file-upload ${document ? 'has-file' : ''}`}>
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={(e) => setDocument(e.target.files?.[0] || null)}
                style={{ display: 'none' }}
                id="file-upload"
              />
              <label htmlFor="file-upload" style={{ cursor: 'pointer' }}>
                {document ? (
                  <div>
                    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14,2 14,8 20,8"/>
                    </svg>
                    <p>{document.name}</p>
                  </div>
                ) : (
                  <div>
                    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                      <polyline points="17,8 12,3 7,8"/>
                      <line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                    <p>Click to upload Aadhaar document</p>
                    <span className="form-help">PDF, JPG, PNG (max 10MB)</span>
                  </div>
                )}
              </label>
            </div>
          </div>

          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Processing...' : 'Submit for AI Verification'}
          </button>
        </form>
      </div>
    </div>
  )
}
