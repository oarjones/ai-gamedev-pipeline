import { useState, useEffect, useRef } from 'react';

const BASE_WS = (import.meta.env.VITE_GATEWAY_URL as string | undefined)?.replace(/^http/, 'ws') ?? 'ws://127.0.0.1:8000'
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined

export function useWebSocket(path: string) {
    const [lastMessage, setLastMessage] = useState<any>(null);
    const ws = useRef<WebSocket | null>(null);

    useEffect(() => {
        if (!path) return;

        const url = new URL(path, BASE_WS);
        if (API_KEY) {
            url.searchParams.set('apiKey', API_KEY);
        }

        ws.current = new WebSocket(url.toString());

        ws.current.onopen = () => {
            console.log(`WebSocket connected to ${path}`);
        };

        ws.current.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                setLastMessage(message);
            } catch (error) {
                console.error("Failed to parse WebSocket message:", error);
            }
        };

        ws.current.onerror = (error) => {
            console.error("WebSocket error:", error);
        };

        ws.current.onclose = () => {
            console.log(`WebSocket disconnected from ${path}`);
        };

        // Cleanup on unmount
        return () => {
            ws.current?.close();
        };
    }, [path]);

    return { lastMessage };
}