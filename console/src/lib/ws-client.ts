import type { RunEvent } from '@/types/api';

export class RunEventStream {
  private ws: WebSocket | null = null;
  private listeners: ((event: RunEvent) => void)[] = [];

  constructor(
    private runId: string,
    private baseUrl = typeof window !== 'undefined'
      ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
      : 'ws://localhost:8080',
  ) {}

  connect(): void {
    this.ws = new WebSocket(`${this.baseUrl}/ws/runs/${this.runId}`);
    this.ws.onmessage = (msg) => {
      const event = JSON.parse(msg.data) as RunEvent;
      this.listeners.forEach((fn) => fn(event));
    };
    this.ws.onclose = () => { this.ws = null; };
  }

  onEvent(listener: (event: RunEvent) => void): () => void {
    this.listeners.push(listener);
    return () => { this.listeners = this.listeners.filter((fn) => fn !== listener); };
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
