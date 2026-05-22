import { render } from 'preact';
import './style.css';
import { App } from './layout/app';

const appRoot = document.getElementById('app');
if (appRoot) {
  render(<App />, appRoot);
}
