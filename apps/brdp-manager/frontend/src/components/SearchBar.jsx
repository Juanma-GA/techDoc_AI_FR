import styles from './SearchBar.module.css';

/**
 * Search bar component
 * Real-time search across all BRDP fields
 * @param {Object} props - Component props
 * @param {string} props.value - Current search value
 * @param {Function} props.onChange - Callback when search value changes
 * @returns {JSX.Element} Search input component
 */
export default function SearchBar({ value, onChange }) {
  return (
    <div className={styles.container}>
      <input
        type="text"
        placeholder="Search across all fields..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={styles.input}
      />
      {value && (
        <button
          onClick={() => onChange('')}
          className={styles.clearBtn}
          aria-label="Clear search"
        >
          ✕
        </button>
      )}
    </div>
  );
}
