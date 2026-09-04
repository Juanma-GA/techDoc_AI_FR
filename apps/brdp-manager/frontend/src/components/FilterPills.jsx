import styles from './FilterPills.module.css';

const FILTER_OPTIONS = ['All', 'Validated', 'Refused', 'Pending'];

/**
 * Filter pills component
 * Toggle filters for BRDP validation status
 * @param {Object} props - Component props
 * @param {string} props.activeFilter - Currently active filter
 * @param {Function} props.onFilterChange - Callback when filter changes
 * @returns {JSX.Element} Filter pill buttons
 */
export default function FilterPills({ activeFilter, onFilterChange }) {
  /**
   * Get CSS class for a filter pill
   * @param {string} option - Filter option
   * @returns {string} Combined class name
   */
  const getPillClass = (option) => {
    let classes = `${styles.pill}`;

    if (activeFilter === option) {
      classes += ` ${styles.active}`;
      if (option === 'All') classes += ` ${styles.allActive}`;
      if (option === 'Validated') classes += ` ${styles.validatedActive}`;
      if (option === 'Refused') classes += ` ${styles.refusedActive}`;
      if (option === 'Pending') classes += ` ${styles.pendingActive}`;
    }

    return classes;
  };

  return (
    <div className={styles.container}>
      {FILTER_OPTIONS.map((option) => (
        <button
          key={option}
          onClick={() => onFilterChange(option)}
          className={getPillClass(option)}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
