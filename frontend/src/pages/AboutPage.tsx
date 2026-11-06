import { useEffect } from "react";
import { Link, useLocation } from "react-router";
import { DISCLAIMER_TEXT } from "../components/Disclaimer";

const CREDITS: { name: string; use: string; license: string; url: string }[] = [
  {
    name: "WoundTissue (Kabir et al., 2025)",
    use: "Imágenes y máscaras de tejido con las que se entrenó el modelo experimental",
    license: "CC BY-NC-SA 4.0 (uso no comercial)",
    url: "https://github.com/akabircs/WoundTissue",
  },
  {
    name: "ResNet-18 preentrenada en ImageNet (torchvision)",
    use: "Encoder inicial del modelo",
    license: "BSD-3-Clause",
    url: "https://pytorch.org/vision/stable/models/resnet.html",
  },
  { name: "PyTorch", use: "Entrenamiento e inferencia", license: "BSD-3-Clause", url: "https://pytorch.org" },
  { name: "OpenCV y OpenCV.js", use: "Procesamiento de imágenes (servidor y navegador)", license: "Apache 2.0", url: "https://opencv.org" },
  { name: "FastAPI", use: "API REST", license: "MIT", url: "https://fastapi.tiangolo.com" },
  { name: "React", use: "Interfaz web", license: "MIT", url: "https://react.dev" },
];

export function AboutPage() {
  const { hash } = useLocation();
  // React Router no desplaza la página hasta el ancla (#creditos): se hace aquí.
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView?.();
  }, [hash]);

  return (
    <>
      <title>Acerca de · DermAI</title>
      <div className="page-header">
        <h1>Acerca de DermAI</h1>
        <p className="lead">
          Prototipo de investigación educativa que une Ingeniería de Sistemas y Medicina: explora cómo el
          procesamiento de imágenes y el aprendizaje profundo pueden describir de forma reproducible las
          características visuales de lesiones cutáneas, con especial interés en el tejido necrótico.
        </p>
      </div>

      <div className="prose stack">
        <section className="card" aria-labelledby="about-scope">
          <h2 id="about-scope">Qué hace y qué no hace</h2>
          <ul>
            <li>Mide características visuales de una fotografía: color, textura, bordes y forma de la lesión.</li>
            <li>Estima qué parte de la lesión tiene rasgos compatibles con tejido necrótico.</li>
            <li>
              <strong>No diagnostica</strong>, no ha sido validado clínicamente y no sustituye la valoración de un
              profesional sanitario.
            </li>
          </ul>
        </section>

        <section className="card" aria-labelledby="about-methods">
          <h2 id="about-methods">Métodos</h2>
          <dl className="definition-list">
            <dt>Heurística de OpenCV</dt>
            <dd>
              Normaliza el tamaño y el color, separa la lesión de la piel de alrededor y clasifica sus píxeles por
              color (negro, amarillo y rojo). No aprende de datos; sus umbrales son fijos.
            </dd>
            <dt>Modelo experimental de PyTorch</dt>
            <dd>
              Red U-Net que segmenta tejidos de herida. Es una <strong>prueba de concepto</strong> entrenada con solo
              13 imágenes públicas: sus métricas no son representativas y falla con fotos distintas a las de
              entrenamiento.
            </dd>
          </dl>
        </section>

        <section className="card" aria-labelledby="about-privacy">
          <h2 id="about-privacy">Privacidad</h2>
          <ul>
            <li>No se piden datos personales. Usa solo imágenes que no identifiquen a nadie.</li>
            <li>Al subir una foto se eliminan sus metadatos (EXIF, ubicación GPS, cámara y fecha).</li>
            <li>Las imágenes se guardan en el servidor local y puedes eliminarlas, junto con sus análisis, en cualquier momento.</li>
            <li>
              En la versión publicada en GitHub Pages, el análisis se hace en tu navegador con OpenCV.js: las fotos no
              se envían a ningún servidor y se guardan solo en este navegador.
            </li>
            <li>
              El prototipo no tiene usuarios ni contraseñas: está pensado para ejecutarse en un equipo local, no para
              publicarse en internet.
            </li>
          </ul>
        </section>

        <section className="card" aria-labelledby="about-limits">
          <h2 id="about-limits">Limitaciones principales</h2>
          <ul>
            <li>Los resultados dependen de la iluminación, la cámara, el encuadre y el tono de piel; su sesgo no está evaluado.</li>
            <li>La heurística mide color, no identifica tejidos: un eritema puede aparecer como «rojo».</li>
            <li>La confianza del modelo no está calibrada: puede ser alta aunque el resultado sea incorrecto.</li>
            <li>No hay validación con profesionales ni con pacientes.</li>
          </ul>
        </section>

        <section className="card" aria-labelledby="about-credits" id="creditos">
          <h2 id="about-credits">Créditos y licencias</h2>
          <table className="metrics-table credits-table" aria-labelledby="about-credits">
            <thead>
              <tr>
                <th scope="col">Recurso</th>
                <th scope="col">Uso</th>
                <th scope="col">Licencia</th>
              </tr>
            </thead>
            <tbody>
              {CREDITS.map((credit) => (
                <tr key={credit.name}>
                  <th scope="row">
                    <a href={credit.url} target="_blank" rel="noreferrer">
                      {credit.name}
                    </a>
                  </th>
                  <td>{credit.use}</td>
                  <td>{credit.license}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">
            Por la licencia de WoundTissue, el modelo entrenado solo puede usarse con fines no comerciales. Cita:
            M. A. Kabir et al., «Deep Learning for Wound Tissue Segmentation: A Comprehensive Evaluation using A Novel
            Dataset», arXiv:2502.10652, 2025.
          </p>
        </section>

        <aside className="alert alert--warning">
          <p className="alert__title">Aviso</p>
          <p>{DISCLAIMER_TEXT} Los resultados no deben usarse para tomar decisiones clínicas.</p>
        </aside>

        <p>
          <Link to="/" className="button button--primary">
            Analizar una imagen
          </Link>
        </p>
      </div>
    </>
  );
}
