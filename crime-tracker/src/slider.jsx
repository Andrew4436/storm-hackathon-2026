// Stormhacks 2026
// function for the slider

import { useState } from "react";

function Slider() {
  const [value, setValue] = useState(2025);

  return (
    <div className="slider">
        // todo: add months
      <input
        type="range"
        min="2003"
        max="2025"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />

      <p>Year: {value}</p>
    </div>
  );
}

export default Slider;