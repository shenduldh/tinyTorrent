export interface PieceResult {
	pieceIndex: number;
	workerIndex: number;
	content: Uint8Array;
}

export interface PieceWork {
	pieceIndex: number;
	hash: Sha1Hash;
	length: number; // piece length in bytes
	ttl: number; // used for preventing forever loop
}

export type Sha1Hash = Uint8Array; // 20 bytes

export interface Torrent {
	trackerURL: string;
	length: number;
	filename: string;
	pieceCount: number;
	pieceLength: number; // the last piece may not be this length
	hashes: Sha1Hash[];
	infoHash: Sha1Hash;
	peerID: string;
}

export interface Message {
	id: number;
	payload?: Uint8Array;
}

export interface Peer {
	ip: string;
	port: number;
}
