const API_BASE = '/api/v1';

export async function submitRequest(
  customerId: string,
  oldName: string,
  newName: string,
  document: File | null
): Promise<{ success: boolean; request_id: string; message: string; status: string }> {
  const formData = new FormData();
  formData.append('customer_id', customerId);
  formData.append('old_name', oldName);
  formData.append('new_name', newName);
  if (document) {
    formData.append('document', document);
  }

  const response = await fetch(`${API_BASE}/requests/submit`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Submission failed');
  }

  return response.json();
}

export async function getRequest(requestId: string) {
  const response = await fetch(`${API_BASE}/requests/${requestId}`);
  
  if (!response.ok) {
    throw new Error('Request not found');
  }
  
  return response.json();
}

export async function listRequests(status?: string) {
  const url = status 
    ? `${API_BASE}/requests?status=${status}`
    : `${API_BASE}/requests`;
    
  const response = await fetch(url);
  
  if (!response.ok) {
    throw new Error('Failed to fetch requests');
  }
  
  return response.json();
}

export async function getPendingRequests() {
  const response = await fetch(`${API_BASE}/requests/pending/review`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch pending requests');
  }
  
  return response.json();
}

export async function submitCheckerDecision(
  requestId: string,
  decision: 'APPROVE' | 'REJECT',
  checkerId: string,
  rejectionReason?: string
) {
  const response = await fetch(`${API_BASE}/checker/decide`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      request_id: requestId,
      decision,
      checker_id: checkerId,
      rejection_reason: rejectionReason,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Decision submission failed');
  }

  return response.json();
}

export async function getAuditLogs(requestId: string) {
  const response = await fetch(`${API_BASE}/audit/${requestId}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch audit logs');
  }
  
  return response.json();
}
