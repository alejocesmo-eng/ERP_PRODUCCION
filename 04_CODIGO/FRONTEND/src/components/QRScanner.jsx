// Componente React para escanear en celulares/tablets
import { Html5QrcodeScanner } from "html5-qrcode";
import { useEffect } from "react";

export function QRScanner({ onScanSuccess }) {
  useEffect(() => {
    const scanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 });
    scanner.render((decodedText) => {
      scanner.clear();
      onScanSuccess(decodedText); // Envía la lectura (ej. RET-000154 u OP-2026-0357)
    });
  }, []);

  return <div id="reader"></div>;
}