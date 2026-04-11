export interface ExtractedData {
  name?: string;
  date_of_birth?: string;
  aadhar_number?: string;
  raw_text?: string;
  forgery_flag: boolean;
  document_authentic?: boolean;
}

export interface ConfidenceScore {
  name_change_request_score: number;
  document_to_old_match: number;
  document_to_new_match: number;
  dob_match: number;
  adhar_match: number;
  doc_auth: number;
  overall: number;
  reasoning?: string;
}

export type RequestStatus = 
  | 'DRAFT'
  | 'AI_PROCESSING'
  | 'AI_VERIFIED_PENDING_HUMAN'
  | 'APPROVED'
  | 'REJECTED'
  | 'RPS_UPDATED'
  | 'FAILED';

export type DecisionType = 'APPROVE' | 'REJECT';

export interface PendingRequest {
  request_id: string;
  customer_id: string;
  name: string;
  extracted_data?: ExtractedData;
  confidence_score?: ConfidenceScore;
  ai_summary?: string;
  ai_recommendation?: string;
  status: RequestStatus;
  checker_decision?: DecisionType;
  rps_reference?: string;
  created_at: string;
  updated_at: string;
}
