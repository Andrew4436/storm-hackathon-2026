import Map from "./map";
import Slider from "./slider"
import Legend from "./legend"
import "./App.css"


// Basically main in java/python/ ANYTHING

export default function App() {
  return (
    <section>
    <div>
      <h1>Vancouver Crime Tracker</h1>

    // theyre like lego bricks
    // just add em in the final thing
      <Map />
      <Slider />
      <Legend />
    </div>
    </section>
  );
}
