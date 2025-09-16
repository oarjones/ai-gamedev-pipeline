import React, { useState } from 'react';
import { useAppStore } from '@/store/appStore';

export default function ChatWorkspace() {
  const project_id = useAppStore((s) => s.project_id);
  const [message, setMessage] = useState('');
  const [chatHistory, setChatHistory] = useState<Array<{
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
  }>>([]);

  const handleSendMessage = () => {
    if (!message.trim()) return;

    const newMessage = {
      id: Date.now().toString(),
      role: 'user' as const,
      content: message,
      timestamp: new Date()
    };

    setChatHistory(prev => [...prev, newMessage]);
    setMessage('');

    // Simulate AI response
    setTimeout(() => {
      const aiResponse = {
        id: (Date.now() + 1).toString(),
        role: 'assistant' as const,
        content: `Entiendo tu mensaje: "${message}". Como asistente de IA para desarrollo de videojuegos, estoy aquí para ayudarte con la planificación, desarrollo y resolución de problemas en tu proyecto.`,
        timestamp: new Date()
      };
      setChatHistory(prev => [...prev, aiResponse]);
    }, 1000);
  };

  return (
    <div className="flex-1 flex flex-col bg-white">
      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {chatHistory.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center max-w-md">
              <ChatBotIcon className="w-16 h-16 text-blue-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-600 mb-2">
                ¡Hola! Soy tu asistente de IA
              </h3>
              <p className="text-gray-500 mb-6">
                Estoy aquí para ayudarte a planificar, desarrollar y resolver problemas en tu proyecto de videojuego.
              </p>
              <div className="grid grid-cols-1 gap-2 text-sm">
                <button className="p-3 text-left bg-blue-50 hover:bg-blue-100 rounded-lg border border-blue-200 transition-colors">
                  💡 "¿Cómo puedo mejorar las mecánicas de mi juego?"
                </button>
                <button className="p-3 text-left bg-purple-50 hover:bg-purple-100 rounded-lg border border-purple-200 transition-colors">
                  🎮 "Ayúdame a generar un plan de desarrollo"
                </button>
                <button className="p-3 text-left bg-green-50 hover:bg-green-100 rounded-lg border border-green-200 transition-colors">
                  🚀 "¿Qué tareas debería priorizar?"
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {chatHistory.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.role === 'assistant' && (
                  <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center flex-shrink-0">
                    <ChatBotIcon className="w-5 h-5 text-white" />
                  </div>
                )}
                <div
                  className={`max-w-2xl p-4 rounded-lg ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-50 text-gray-800 border border-gray-200'
                  }`}
                >
                  <p className="text-sm leading-relaxed">{msg.content}</p>
                  <div className={`text-xs mt-2 ${
                    msg.role === 'user' ? 'text-blue-100' : 'text-gray-500'
                  }`}>
                    {msg.timestamp.toLocaleTimeString()}
                  </div>
                </div>
                {msg.role === 'user' && (
                  <div className="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center flex-shrink-0">
                    <UserIcon className="w-5 h-5 text-gray-600" />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 p-4 bg-gray-50">
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              placeholder={
                project_id
                  ? "Escribe tu mensaje al asistente de IA..."
                  : "Selecciona un proyecto para comenzar a chatear..."
              }
              className="w-full p-3 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              rows={3}
              disabled={!project_id}
            />
            <div className="flex items-center justify-between mt-2">
              <div className="text-xs text-gray-500">
                Presiona Enter para enviar, Shift+Enter para nueva línea
              </div>
              <div className="flex items-center gap-2">
                <button className="p-1 text-gray-400 hover:text-gray-600">
                  <AttachIcon className="w-4 h-4" />
                </button>
                <button className="p-1 text-gray-400 hover:text-gray-600">
                  <EmojiIcon className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
          <button
            onClick={handleSendMessage}
            disabled={!message.trim() || !project_id}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            <SendIcon className="w-4 h-4" />
            Enviar
          </button>
        </div>
      </div>
    </div>
  );
}

// Icons
function ChatBotIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M17.5,12A1.5,1.5 0 0,1 16,10.5A1.5,1.5 0 0,1 17.5,9A1.5,1.5 0 0,1 19,10.5A1.5,1.5 0 0,1 17.5,12M10.5,12A1.5,1.5 0 0,1 9,10.5A1.5,1.5 0 0,1 10.5,9A1.5,1.5 0 0,1 12,10.5A1.5,1.5 0 0,1 10.5,12M12,2C13.1,2 14,2.9 14,4C14,5.1 13.1,6 12,6C10.9,6 10,5.1 10,4C10,2.9 10.9,2 12,2M21,9V7H15L13.5,7.5C13.1,4.04 11.36,3 10,3H8C5.24,3 3,5.24 3,8V16L7,20H17C19.76,20 22,17.76 22,15V12C22,10.9 21.1,10 20,10H18V9A1,1 0 0,1 19,8H21M20,15A2,2 0 0,1 18,17H8L5,14V8A2,2 0 0,1 7,6H9V8A2,2 0 0,0 11,10H20V15Z" />
    </svg>
  );
}

function UserIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,4A4,4 0 0,1 16,8A4,4 0 0,1 12,12A4,4 0 0,1 8,8A4,4 0 0,1 12,4M12,14C16.42,14 20,15.79 20,18V20H4V18C4,15.79 7.58,14 12,14Z" />
    </svg>
  );
}

function SendIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M2,21L23,12L2,3V10L17,12L2,14V21Z" />
    </svg>
  );
}

function AttachIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M7.5,18A5.5,5.5 0 0,1 2,12.5A5.5,5.5 0 0,1 7.5,7H18A4,4 0 0,1 22,11A4,4 0 0,1 18,15H9.5A2.5,2.5 0 0,1 7,12.5A2.5,2.5 0 0,1 9.5,10H17V11.5H9.5A1,1 0 0,0 8.5,12.5A1,1 0 0,0 9.5,13.5H18A2.5,2.5 0 0,0 20.5,11A2.5,2.5 0 0,0 18,8.5H7.5A4,4 0 0,0 3.5,12.5A4,4 0 0,0 7.5,16.5H17V18H7.5Z" />
    </svg>
  );
}

function EmojiIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,2C13.1,2 14,2.9 14,4C14,5.1 13.1,6 12,6C10.9,6 10,5.1 10,4C10,2.9 10.9,2 12,2M21,9V7H15L13.5,7.5C13.1,4.04 11.36,3 10,3H8C5.24,3 3,5.24 3,8V16L7,20H17C19.76,20 22,17.76 22,15V12C22,10.9 21.1,10 20,10H18V9A1,1 0 0,1 19,8H21M12,17.5C10.07,17.5 8.5,15.93 8.5,14H15.5C15.5,15.93 13.93,17.5 12,17.5M8.5,11A1.5,1.5 0 0,0 10,9.5A1.5,1.5 0 0,0 8.5,8A1.5,1.5 0 0,0 7,9.5A1.5,1.5 0 0,0 8.5,11M15.5,11A1.5,1.5 0 0,0 17,9.5A1.5,1.5 0 0,0 15.5,8A1.5,1.5 0 0,0 14,9.5A1.5,1.5 0 0,0 15.5,11Z" />
    </svg>
  );
}