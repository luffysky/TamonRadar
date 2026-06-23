export interface CrawlRecord {
  keyword: string;
  category: string;
  title: string;
  url: string;
  domain: string;
  snippet: string;
  price: string;
  image_url: string;
  key_info: string;
  page_title: string;
  status: string;
  google_page: number;
  [key: string]: unknown;
}

export interface Summary {
  total: number;
  with_price: number;
  categories: Record<string, number>;
  domains: Record<string, number>;
}

export interface CrawlResult {
  records: CrawlRecord[];
  summary: Summary;
}

export interface ProgressEvent {
  type: string;
  message?: string;
  current?: number;
  total?: number;
  seq?: number;
  [key: string]: unknown;
}

export interface HistoryRun {
  id: string;
  created_at: string;
  finished_at: string;
  status: string;
  keywords: string[];
  summary: Summary;
}
