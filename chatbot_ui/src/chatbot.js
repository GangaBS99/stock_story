import React, { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import "./style.css";
import axios from "axios";
import Linkify from "linkify-react";
import { toast, ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import Icon from '@mui/material/Icon';

const Chatbot = () => {
  const [messages, setMessages] = useState([
    {
      sender: "bot",
      text: "Hi there! I am Reserach Assistant. How Can I help you today?.",
      suggestions: [
        "create a stock story for TCS  covering the period from 2025-09-01 to 2025-12-31 ",
        "Amazon, 2025-09-01 to 2025-12-31",
        "Infosys, 2025-10-01 to 2026-01-31"
      ]
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [summaries, setSummaries] = useState([]);
  const [currentSummaryIndex, setCurrentSummaryIndex] = useState(0);
  const [wsConnected, setWsConnected] = useState(false);
  const chatRef = useRef(null);

  const sessionId = "user_abc_001";

  const connectWebSocket = () => {
    const socket = new WebSocket("ws://localhost:8000/ws/summary");
    let pingInterval;

    socket.onopen = () => {
      setWsConnected(true);
      console.log("✅ WebSocket connected");
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.summary && data.summary.trim() !== "") {
          const newSummary = {
            date_range: data.date_range,
            summary: data.summary,
          };

          setSummaries((prev) => {
            const isDuplicate = prev.some(
              (s) =>
                s.date_range === newSummary.date_range &&
                s.summary === newSummary.summary
            );

            if (!isDuplicate) {
              console.log("✅ New summary received:", newSummary);

              // Add summary bubble only once in the messages timeline
              setMessages((prevMessages) => {
                const hasSummary = prevMessages.some(
                  (msg) => msg.type === "summary"
                );
                if (!hasSummary) {
                  const lastUserIndex = [...prevMessages]
                    .reverse()
                    .findIndex((msg) => msg.sender === "user");
                  const insertIndex =
                    lastUserIndex === -1
                      ? prevMessages.length
                      : prevMessages.length - lastUserIndex;

                  const newMessages = [...prevMessages];
                  newMessages.splice(insertIndex, 0, { type: "summary" });
                  return newMessages;
                }
                return prevMessages;
              });

              return [...prev, newSummary];
            } else {
              console.log("⚠️ Duplicate summary ignored:", newSummary);
              return prev;
            }
          });
        }
      } catch (error) {
        console.error("❌ WebSocket message parsing error:", error);
      }
    };

    socket.onerror = () => {
      console.error("❌ WebSocket error");
      // toast.error("WebSocket connection error!");
    };

    socket.onclose = () => {
      console.warn("🔌 WebSocket disconnected");
      setWsConnected(false);
      // toast.warn("Connection lost. Attempting to reconnect...");
      setTimeout(connectWebSocket, 3000); // Retry after 3 seconds
    };

    pingInterval = setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send("ping");
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      socket.close();
    };
  };

  useEffect(() => {
    const disconnect = connectWebSocket();
    return disconnect;
  }, []);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages, summaries]);

  useEffect(() => {
    if (summaries.length > 0) {
      setCurrentSummaryIndex(summaries.length - 1);
    }
  }, [summaries]);

  const handleSend = async (message = input) => {
    if (!message.trim()) return;

    const userMsg = { sender: "user", text: message };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const response = await axios.post(
        "http://localhost:8000/process_message",
        {
          message: message,
          session_id: sessionId,
        }
      );

      const botReply =
        response.data.output || "Sorry, I didn't understand that.";
      const botSuggestions = response.data.suggestions || [];
      
      setMessages((prev) => [...prev, { 
        sender: "bot", 
        text: botReply,
        suggestions: botSuggestions
      }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          sender: "bot",
          text: "⚠️ Error fetching response. Please try again later.",
        },
      ]);
    }

    setInput("");
    setLoading(false);
  };

  const linkifyOptions = {
    defaultProtocol: "https",
    target: "_blank",
    className: "linkified",
  };

  return (
    <div className="wrapper">
      <ToastContainer />
      <header>
        <span className="logo">📈</span>
        <h1>Research Assistant</h1>
      </header>

      <div className="chat" ref={chatRef}>
        {messages.map((msg, i) => {
          if (msg.type === "summary") {
            return (
              <motion.div
                key={i}
                className="bubble left bot"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <span className="emoji">🤖</span>
                <span>
                  <Linkify options={linkifyOptions}>
                    📆{" "}
                    <strong>
                      {summaries[currentSummaryIndex]?.date_range}
                    </strong>
                    <br />
                    <br />
                    {summaries[currentSummaryIndex]?.summary}
                  </Linkify>
                </span>
                <div className="carousel-buttons">
                  {summaries.map((_, index) => (
                    <button
                      key={index}
                      className={`carousel-btn ${
                        index === currentSummaryIndex ? "active" : ""
                      }`}
                      onClick={() => setCurrentSummaryIndex(index)}
                    >
                      {index + 1}
                    </button>
                  ))}
                </div>
              </motion.div>
            );
          } else {
            return (
              <React.Fragment key={i}>
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                  className={`bubble ${
                    msg.sender === "user" ? "right user" : "left bot"
                  }`}
                >
                  <span className="emoji">
                    {msg.sender === "user" ? "👩🏻💼" : "🤖"}
                  </span>
                  <span>
                    <Linkify options={linkifyOptions}>{msg.text}</Linkify>
                  </span>
                </motion.div>
                {msg.suggestions && msg.suggestions.length > 0 && (
                  <div className="message-suggestions">
                    {msg.suggestions.map((suggestion, idx) => (
                      <button
                        key={idx}
                        className="suggestion-chip"
                        onClick={() => handleSend(suggestion)}
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                )}
              </React.Fragment>
            );
          }
        })}

        {loading && (
          <motion.div
            className="bubble left bot"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <span className="emoji">🤖</span>
            <span>Typing...</span>
          </motion.div>
        )}
      </div>

      <div className="input-area">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Please give company name and date range..."
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
        />
        <button onClick={handleSend}>➤</button>
      </div>
    </div>
  );
};

export default Chatbot;
