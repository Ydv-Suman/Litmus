function JobSelect({
  jobs,
  message,
  name,
  onChange,
  required = false,
  status,
  value,
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-semibold text-slate-800">
        Job opening
      </span>
      <select
        className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:bg-white"
        disabled={status !== 'success' || jobs.length === 0}
        name={name}
        onChange={onChange}
        required={required}
        value={value}
      >
        <option value="">
          {status === 'loading'
            ? 'Loading jobs...'
            : jobs.length === 0
              ? 'No jobs available'
              : 'Select a job'}
        </option>
        {jobs.map((job) => (
          <option key={job.id} value={job.id}>
            {job.title}
          </option>
        ))}
      </select>
      {status === 'success' && jobs.length > 0 ? null : (
        <p className="mt-2 text-sm text-slate-500">{message}</p>
      )}
    </label>
  )
}

export default JobSelect
