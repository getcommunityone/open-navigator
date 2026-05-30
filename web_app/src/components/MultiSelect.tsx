import Select, { MultiValue, components, OptionProps, MultiValueGenericProps } from 'react-select'

interface OptionType {
  value: string
  label: string
  count?: number
}

interface MultiSelectProps {
  label: string
  options: OptionType[]
  selected: string[]
  onChange: (selected: string[]) => void
  placeholder?: string
  className?: string
}

// Custom option component to show counts
const CustomOption = (props: OptionProps<OptionType>) => {
  const { data } = props
  return (
    <components.Option {...props}>
      <div className="flex items-center justify-between w-full">
        <span>{data.label}</span>
        {data.count !== undefined && (
          <span className="text-xs text-gray-500 ml-2">
            ({data.count.toLocaleString()})
          </span>
        )}
      </div>
    </components.Option>
  )
}

// Custom multi-value label to show abbreviated text
const CustomMultiValueLabel = (props: MultiValueGenericProps<OptionType>) => {
  return (
    <components.MultiValueLabel {...props}>
      <span className="truncate max-w-[100px]" title={props.data.label}>
        {props.data.label}
      </span>
    </components.MultiValueLabel>
  )
}

export default function MultiSelect({
  label,
  options,
  selected,
  onChange,
  placeholder = 'Select...',
  className = ''
}: MultiSelectProps) {
  const selectedOptions = options.filter(opt => selected.includes(opt.value))

  const handleChange = (newValue: MultiValue<OptionType>) => {
    onChange(newValue.map(opt => opt.value))
  }

  return (
    <div className={className}>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
      </label>
      <Select<OptionType, true>
        isMulti
        options={options}
        value={selectedOptions}
        onChange={handleChange}
        placeholder={placeholder}
        components={{ 
          Option: CustomOption,
          MultiValueLabel: CustomMultiValueLabel
        }}
        className="react-select-container"
        classNamePrefix="react-select"
        styles={{
          control: (base, state) => ({
            ...base,
            minHeight: '38px',
            borderColor: state.isFocused ? '#3b82f6' : '#d1d5db',
            boxShadow: state.isFocused ? '0 0 0 1px #3b82f6' : 'none',
            '&:hover': {
              borderColor: state.isFocused ? '#3b82f6' : '#9ca3af'
            }
          }),
          placeholder: (base) => ({
            ...base,
            color: '#9ca3af'
          }),
          singleValue: (base) => ({
            ...base,
            color: '#111827'
          }),
          input: (base) => ({
            ...base,
            color: '#111827'
          }),
          menu: (base) => ({
            ...base,
            zIndex: 50
          }),
          menuList: (base) => ({
            ...base,
            maxHeight: '320px'
          }),
          option: (base, state) => ({
            ...base,
            color: '#111827',
            backgroundColor: state.isFocused ? '#f3f4f6' : 'white',
            '&:active': {
              backgroundColor: '#e5e7eb'
            }
          }),
          multiValue: (base) => ({
            ...base,
            backgroundColor: '#dbeafe',
            borderRadius: '4px'
          }),
          multiValueLabel: (base) => ({
            ...base,
            color: '#1e40af',
            fontSize: '0.875rem'
          }),
          multiValueRemove: (base) => ({
            ...base,
            color: '#1e40af',
            ':hover': {
              backgroundColor: '#bfdbfe',
              color: '#1e3a8a'
            }
          })
        }}
      />
    </div>
  )
}
