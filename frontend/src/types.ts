export type Reply = { content: string; at: string };

export type Entry = {
  id: number;
  name: string;
  /** 비밀글이면 서버가 이 키 자체를 응답에 담지 않는다 */
  content?: string;
  is_secret: boolean;
  photo: string | null;
  reply?: Reply | null;
  created_at: string;
  updated_at: string | null;
  mine: boolean;
};

export type Feed = {
  entries: Entry[];
  total: number;
  has_more: boolean;
};
